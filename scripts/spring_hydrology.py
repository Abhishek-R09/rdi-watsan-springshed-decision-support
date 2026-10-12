"""DEM hydrology at a spring: drainage area, wetness index and distance to stream.

Works on a window of the Copernicus 30 m DEM around each spring (default +/- 5 km,
widened to +/- 20 km when the spring's D8 catchment reaches the window edge).

Steps:
1. Fill depressions (pyflwdir, Wang and Liu 2006) so every cell drains to the window edge.
2. D8 flow directions and upstream area. Cells draining at least STREAM_THRESHOLD_KM2
   form the stream network; Strahler order and height above the nearest drainage (HAND)
   are computed on it.
3. Multiple-flow-direction (MFD, Freeman 1991, exponent 1.1) upstream area on the filled
   DEM. MFD spreads flow over all lower neighbours, so it is far less sensitive than D8 to
   a coordinate being one cell off a hollow. It is the area used for the wetness index.
4. Topographic wetness index TWI = ln(a / tan b), with a = MFD area / cell width (m) and
   b = local slope (minimum tan b 0.001).

Values describe the DEM cell at the coordinate as given. A 30 m DEM cannot see the
small hollows many springs sit in, and GPS errors of 10-30 m move a spring between
cells, so the 3 x 3 maximum is reported alongside the cell value.
Requires: pip install pyflwdir (pulls in numba).
"""

import math

import numpy as np
import pyflwdir
from numba import njit
from scipy.ndimage import distance_transform_edt

STREAM_THRESHOLD_KM2 = 0.5
WINDOWS_M = (5000, 20000)
MFD_EXPONENT = 1.1
NODATA = -9999.0


@njit(cache=True)
def _mfd_area(z, cell_area, dx, dy, d8_down, exponent):
    """Freeman (1991) multiple-flow-direction accumulation, in m2. z must be depression-filled."""
    nrow, ncol = z.shape
    order = np.argsort(-z.ravel())
    acc = cell_area.copy()
    drs = (-1, -1, -1, 0, 0, 1, 1, 1)
    dcs = (-1, 0, 1, -1, 1, -1, 0, 1)
    weights = np.zeros(8)
    for k in range(order.size):
        idx = order[k]
        r, c = idx // ncol, idx % ncol
        if z[r, c] == -9999.0:
            continue
        total = 0.0
        for n in range(8):
            rr, cc = r + drs[n], c + dcs[n]
            weights[n] = 0.0
            if 0 <= rr < nrow and 0 <= cc < ncol and z[rr, cc] != -9999.0 and z[rr, cc] < z[r, c]:
                dist = math.hypot(drs[n] * dy, dcs[n] * dx)
                w = ((z[r, c] - z[rr, cc]) / dist) ** exponent
                if drs[n] != 0 and dcs[n] != 0:
                    w *= 0.354  # diagonal contour length, Quinn et al. 1991
                else:
                    w *= 0.5
                weights[n] = w
                total += w
        if total > 0:
            for n in range(8):
                if weights[n] > 0:
                    acc[r + drs[n], c + dcs[n]] += acc[r, c] * weights[n] / total
        else:  # flat after filling: follow the D8 direction
            down = d8_down[r, c]
            if down >= 0 and down != idx:
                acc[down // ncol, down % ncol] += acc[r, c]
    return acc


def _window_hydrology(z, transform, row, col, lat, metres_per_degree):
    m_lat, m_lon = metres_per_degree(lat)
    dx, dy = abs(transform.a) * m_lon, abs(transform.e) * m_lat
    flw = pyflwdir.from_dem(z, nodata=NODATA, transform=transform, latlon=True, outlets="edge")
    filled = pyflwdir.dem.fill_depressions(z, nodata=NODATA)[0]
    basin = flw.basins(idxs=np.array([row * z.shape[1] + col]))
    touches_edge = bool(basin[0, :].any() or basin[-1, :].any() or basin[:, 0].any() or basin[:, -1].any())
    upa_d8 = flw.upstream_area(unit="km2")
    streams = upa_d8 >= STREAM_THRESHOLD_KM2
    down = flw.idxs_ds.reshape(z.shape).astype(np.int64)
    cell_area = np.full(z.shape, dx * dy)
    acc = _mfd_area(filled.astype(np.float64), cell_area, dx, dy, down, MFD_EXPONENT)
    gy, gx = np.gradient(z.astype(np.float64), dy, dx)
    tan_b = max(float(np.hypot(gx[row, col], gy[row, col])), 0.001)
    width = (dx + dy) / 2
    result = {
        "dem_drainage_area_ha": acc[row, col] / 1e4,
        "dem_drainage_area_max30m_ha": acc[row - 1:row + 2, col - 1:col + 2].max() / 1e4,
        "dem_drainage_area_d8_ha": upa_d8[row, col] * 100,
        "dem_twi": math.log((acc[row, col] / width) / tan_b),
        "dem_catchment_window_edge": "Y" if touches_edge else "",
    }
    if streams.any():
        dist, (ir, ic) = distance_transform_edt(~streams, sampling=(dy, dx), return_indices=True)
        sr, sc = ir[row, col], ic[row, col]
        order = flw.stream_order(type="strahler", mask=streams)
        hand = flw.hand(drain=streams, elevtn=filled)
        result.update({
            "dem_distance_to_stream_m": dist[row, col],
            "dem_nearest_stream_order": int(order[sr, sc]),
            "dem_nearest_stream_area_km2": upa_d8[sr, sc],
            "dem_height_above_stream_m": hand[row, col] if hand[row, col] >= 0 else None,
        })
    return result


def hydrology_features(read_window, centre_index, metres_per_degree, dem_sets, lon, lat):
    """Return the hydrology columns for one spring, or {} when the DEM window is unusable."""
    result = {}
    for radius in WINDOWS_M:
        z, transform = read_window(dem_sets, lon, lat, radius)
        if z is None:
            return {}
        z = z.astype(np.float32)
        z[z <= -1000] = NODATA
        row, col = centre_index(transform, lon, lat)
        if not (1 <= row < z.shape[0] - 1 and 1 <= col < z.shape[1] - 1) or z[row, col] == NODATA:
            return {}
        result = _window_hydrology(z, transform, row, col, lat, metres_per_degree)
        if not result["dem_catchment_window_edge"]:
            break
    return result

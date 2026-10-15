"""Module B: the likely recharge zone (springshed) of one spring, drawn on the map.

There is no ready-made "point in, springshed out" method (docs: Project1 plan, section 4.4), so this is a
transparent hybrid that a geologist can check and correct in the field:

1. Surface catchment. The 30 m Copernicus DEM is depression-filled and routed (D8, pyflwdir). The land draining
   to the spring cell is its surface catchment. A 30 m DEM and a phone GPS can both be one cell off, so the
   catchments of the 8 cells around the spring are also allowed (unless a cell is a stream).
2. Search area. Recharge happens uphill of the outlet and within a limited height above it. Delineated springsheds
   in Garhwal span 80-360 m of relief (Rathi 2021, 35 springs) and the RDI Chamba springs 160-490 m, so cells from
   the spring level up to HEIGHT_ABOVE_M above it and within MAX_DISTANCE_M are searched. The zone may cross the
   ridge by a narrow margin (DEM error), and further when the field form says the rock layers tilt down towards the
   spring from beyond it (dip direction).
3. Recharge potential. Every cell gets a 0-1 score from slope, land cover, rock type and distance to faults or
   lineaments, with the weights and class scores in config/module_b_recharge_factors_v1.csv (AHP-style overlay,
   Nijesh 2024 / Joshi 2024; weights are a draft for WATSAN to change).
4. Size. The target area comes from the spring's peak (monsoon) flow, using the area-flow relation fitted to the
   35 Rathi (2021) springsheds; with no flow reading, the typical 1-10 ha of delineated hill springsheds is used.
5. Zone. From the spring, cells are added uphill one at a time, best first (high potential, close to the spring),
   without crossing a stream channel or (for the small and likely zones) a mapped GSI fault, until each target
   area is reached. Three nested zones come out: small, likely and large.

The result is a first estimate from maps, never a substitute for walking the zone with a geologist.
Usage (one spring):
    python scripts/module_b_springshed.py --lat 29.91903 --lon 78.55647 [--elevation 1481] [--monsoon-flow-lpm 12]
           [--dip-direction 220 --dip-angle 30] [--geojson out.geojson]
Layers are read with scripts/build_spring_features.py through Module A's LayerSession (--cache, --local-layers).
"""

from __future__ import annotations

import argparse
import base64
import csv
import heapq
import json
import math
import os
import statistics
import struct
import sys
import zlib
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

FACTORS_CSV = ROOT / "config" / "module_b_recharge_factors_v1.csv"
LITERATURE_CSV = ROOT / "data" / "01_staged" / "literature" / "csv" / "literature_spring_records_common_v1.csv"
INPUT_CSV = ROOT / "data" / "02_processed" / "spring_master" / "spring_master_v1_input.csv"

WINDOW_M = 2300  # DEM read around the spring (half-width)
MAX_DISTANCE_M = 2000  # farthest a zone cell may be from the spring
HEIGHT_ABOVE_M = 400  # highest a zone cell may be above the spring
BELOW_TOLERANCE_M = 3  # DEM noise: cells this much below the spring still count as level with it
STREAM_BARRIER_KM2 = 0.5  # D8 drainage area at which a channel is a stream the zone does not cross
STREAM_DISPLAY_KM2 = 0.1  # smaller channels are shown on the map but are not barriers
NEAR_SPRING_M = 90  # stream and fault barriers do not apply this close to the spring
RIDGE_MARGIN_M = 60  # small and likely zones may cross the catchment divide by this much (DEM error)
WIDE_MARGIN_M = 150  # the large zone may reach this far beyond the divide
DIP_SECTOR_DEG = 40  # half-width of the up-dip search sector when the rock tilt is known
MIN_DIP_DEG = 5
DISTANCE_SCALE_M = 600  # closeness to the spring breaks ties between equally good cells
DEFAULT_AREA_HA = (1.5, 3.0, 8.0)  # small / likely / large without a flow reading
SPOT_SEPARATION_M = 150
NODATA = -9999.0

WORLDCOVER = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
              60: "Bare / sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
              90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen"}
LEGEND = [("Very low", (255, 255, 204, 70)), ("Low", (217, 240, 163, 120)), ("Medium", (173, 221, 142, 150)),
          ("High", (65, 171, 93, 170)), ("Very high", (0, 104, 55, 190))]


# --------------------------------------------------------------------------- tables
@lru_cache(maxsize=1)
def load_factors(path=FACTORS_CSV):
    """factor id -> {"name", "weight", "why", "classes": {class: score}} in file order."""
    factors = {}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            f = factors.setdefault(row["factor"], {"name": row["factor_name"], "weight": float(row["weight_pct"]),
                                                   "why": row["why"], "classes": {}})
            f["classes"][row["class"]] = float(row["score"])
            if row["why"] and not f["why"]:
                f["why"] = row["why"]
    return factors


@lru_cache(maxsize=1)
def rathi_fit():
    """Power law area_ha = a * peak_flow_lpm ** b fitted (log-log least squares) to the 35 Rathi (2021) springsheds.
    Their areas were tuned by the authors to follow an area-flow relation, so the scatter understates the real error."""
    q, area = [], []
    with LITERATURE_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["record_id"].startswith("RAT-") and row["discharge_max_m3_per_day_source_value"] and row["springshed_area_km2_source_value"]:
                q.append(float(row["discharge_max_m3_per_day_source_value"]) * 1000 / 1440)
                area.append(float(row["springshed_area_km2_source_value"]) * 100)
    b, log_a = np.polyfit(np.log(q), np.log(area), 1)
    return {"a": float(math.exp(log_a)), "b": float(b), "n": len(q), "q_range": (min(q), max(q))}


@lru_cache(maxsize=1)
def monsoon_to_lean_ratio():
    """Median monsoon / lean-season flow among the input springs with two different readings (never the test springs).
    Most WATSAN rows repeat one reading in both columns; those say nothing about the ratio and are skipped."""
    ratios = []
    with INPUT_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                dry, wet = float(row["discharge_dry_lpm"]), float(row["discharge_monsoon_lpm"])
            except (KeyError, ValueError):
                continue
            if dry > 0 and wet > dry:
                ratios.append(wet / dry)
    return (statistics.median(ratios), len(ratios)) if ratios else (3.0, 0)


def target_area(field):
    """Small / likely / large target areas (ha) and the reason, from the flow readings on the field form."""
    fit = rathi_fit()
    monsoon, lean = _number(field.get("monsoon_flow_lpm")), _number(field.get("lean_flow_lpm"))
    if monsoon and monsoon > 0:
        likely, spread = fit["a"] * monsoon ** fit["b"], 2.0
        basis = (f"Sized from the monsoon flow ({monsoon:g} L/min) with the area-flow relation of {fit['n']} delineated "
                 f"Garhwal springsheds (Rathi 2021): area = {fit['a']:.3f} x flow^{fit['b']:.2f}.")
        if monsoon > fit["q_range"][1] * 1.5 or monsoon < fit["q_range"][0] / 1.5:
            spread = 3.0
            basis += f" That flow is outside the {fit['q_range'][0]:.0f}-{fit['q_range'][1]:.0f} L/min those springs cover, so the range is wider."
        kind = "monsoon flow"
    elif lean and lean > 0:
        ratio, n = monsoon_to_lean_ratio()
        peak = lean * ratio
        likely, spread = fit["a"] * peak ** fit["b"], 2.5
        basis = (f"Sized from the lean-season flow ({lean:g} L/min) times {ratio:.1f}, the median monsoon/lean ratio of {n} "
                 f"springs in the data, with the Rathi (2021) area-flow relation. A monsoon reading would narrow this.")
        kind = "lean flow"
    else:
        small, likely, large = DEFAULT_AREA_HA
        return {"low": small, "mid": likely, "high": large, "kind": "default",
                "basis": "No flow reading was given, so the typical size of delineated hill springsheds (1-10 ha; Rathi 2021, "
                         "Spring Atlas profiles) was used. A monsoon flow reading would size it for this spring."}
    likely = max(likely, 0.5)
    return {"low": round(max(likely / spread, 0.3), 2), "mid": round(likely, 2), "high": round(likely * spread, 2),
            "kind": kind, "basis": basis}


def _number(value):
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def rock_classes(text):
    """Rock classes named in a GSI lithology text, e.g. ["Phyllite", "Quartzite", "Carbonate"]; ["Other"] if none."""
    from build_spring_master import LITHOLOGY_CLASSES
    lowered, hits = (text or "").lower(), []
    for key, label in LITHOLOGY_CLASSES:
        if key in lowered and label not in hits:
            hits.append(label)
    return hits or ["Other"]


def slope_class(deg):
    return "0-10 degrees" if deg < 10 else "10-20 degrees" if deg < 20 else "20-30 degrees" if deg < 30 else "30-40 degrees" if deg < 40 else "over 40 degrees"


def structure_class(dist):
    return "within 100 m" if dist <= 100 else "100-250 m" if dist <= 250 else "250-500 m" if dist <= 500 else "over 500 m"


# --------------------------------------------------------------------------- grid helpers
def _grid_coords(shape, t):
    rows, cols = np.indices(shape)
    return t.c + (cols + 0.5) * t.a, t.f + (rows + 0.5) * t.e


def _mask_to_feature(mask, t, properties, smooth_deg):
    """Polygon (WGS84 GeoJSON feature) of the True cells, with the stair-steps of the 30 m grid softened."""
    from rasterio.features import shapes
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    if not mask.any():
        return None
    parts = [shape(geom) for geom, value in shapes(mask.astype("uint8"), mask=mask, transform=t) if value == 1]
    geom = unary_union(parts).buffer(smooth_deg, join_style="round").buffer(-smooth_deg, join_style="round")
    geom = geom.simplify(smooth_deg / 3, preserve_topology=True)
    return {"type": "Feature", "geometry": mapping(geom), "properties": properties}


def _png(rgba):
    """RGBA array -> PNG data URL, written with the standard library (no imaging package needed)."""
    height, width = rgba.shape[:2]
    raw = b"".join(b"\x00" + rgba[r].tobytes() for r in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _lines_in_window(lines, to_lonlat, box_utm, props):
    """GeoJSON line features (WGS84) of the UTM lines that cross the window."""
    from shapely import transform as shapely_transform
    from shapely.geometry import mapping
    features = []
    for geom, p in zip(lines, props):
        part = geom.intersection(box_utm)
        if part.is_empty:
            continue
        part = shapely_transform(part, lambda xy: np.column_stack(to_lonlat(xy[:, 0], xy[:, 1])))
        features.append({"type": "Feature", "geometry": mapping(part), "properties": p})
    return {"type": "FeatureCollection", "features": features}


def _grow(seed, allowed, priority, limit, start=None):
    """Add 4-connected cells from the seed, best priority first. Returns the cells in the order they were added
    (start cells first). 4-connection means a one-cell-wide stream or fault line is a real barrier."""
    nrow, ncol = allowed.shape
    order = list(start or [seed])
    taken = np.zeros(allowed.shape, bool)
    for cell in order:
        taken[cell] = True
    heap = []

    def push_neighbours(r, c):
        for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= rr < nrow and 0 <= cc < ncol and not taken[rr, cc] and allowed[rr, cc]:
                taken[rr, cc] = True
                heapq.heappush(heap, (-priority[rr, cc], rr, cc))

    for r, c in order:
        push_neighbours(r, c)
    while heap and len(order) < limit:
        _, r, c = heapq.heappop(heap)
        order.append((r, c))
        push_neighbours(r, c)
    return order


# --------------------------------------------------------------------------- main
def delineate(inputs, session):
    """Module B under the shared contract (docs/module-contract.md): one spring in, one result dict out.

    inputs: {"spring": {name, latitude, longitude, elevation_m}, "field": {monsoon_flow_lpm, lean_flow_lpm,
             dip_direction_deg, dip_angle_deg, ...}}
    session: Module A's LayerSession (its DEM, WorldCover, GSI geology and lineaments are reused).
    The returned dict also holds "_zones": shapely geometries for Module C; drop keys starting with "_" before saving.
    """
    import pyflwdir
    import rasterio.features
    from pyproj import Transformer
    from scipy.ndimage import binary_dilation, distance_transform_edt
    from shapely import STRtree, box, points as shapely_points
    from shapely.geometry import shape

    spring = inputs["spring"]
    field = inputs.get("field") or {}
    lat, lon = float(spring["latitude"]), float(spring["longitude"])
    given_elevation = _number(spring.get("elevation_m"))
    name = spring.get("name") or f"{lat:.5f}, {lon:.5f}"
    mod = session.mod
    session.ensure(lat, lon)
    layers = session.layers
    warnings, rationale, missing = [], [], []

    def unavailable(reason):
        return {"module": "B", "title": "Springshed and recharge zone", "version": "v1 draft", "status": "unavailable",
                "spring": {"name": name, "latitude": lat, "longitude": lon, "elevation_m": given_elevation},
                "result": None, "confidence": "Low", "rationale": [reason], "missing_inputs": [], "warnings": warnings,
                "report_markdown": f"# Springshed: {name}\n\n{reason}\n", "_zones": None}

    z, t = mod.read_window(layers.dem, lon, lat, WINDOW_M)
    if z is None:
        return unavailable("No elevation map (DEM) covers this location in the map set, so the springshed could not be drawn.")
    z = z.astype(np.float64)
    z[z <= -1000] = NODATA
    row, col = mod.centre_index(t, lon, lat)
    if not (2 <= row < z.shape[0] - 2 and 2 <= col < z.shape[1] - 2) or z[row, col] == NODATA:
        return unavailable("The elevation map has no value at the spring, so the springshed could not be drawn.")
    m_lat, m_lon = mod.metres_per_degree(lat)
    dx, dy = abs(t.a) * m_lon, abs(t.e) * m_lat
    cell_ha = dx * dy / 1e4
    xs, ys = _grid_coords(z.shape, t)
    dist = np.hypot((xs - lon) * m_lon, (ys - lat) * m_lat)
    bearing = (np.degrees(np.arctan2((xs - lon) * m_lon, (ys - lat) * m_lat)) + 360) % 360
    valid = z != NODATA

    # 1. surface catchment
    flw = pyflwdir.from_dem(z.astype(np.float32), nodata=NODATA, transform=t, latlon=True, outlets="edge")
    upa = flw.upstream_area(unit="km2")
    z_s = float(z[row, col])
    idx = lambda r, c: r * z.shape[1] + c  # noqa: E731
    own = flw.basins(idxs=np.array([idx(row, col)])) > 0
    stream = upa >= STREAM_BARRIER_KM2
    outlets = [idx(r, c) for r in range(row - 1, row + 2) for c in range(col - 1, col + 2)
               if (r, c) == (row, col) or not stream[r, c]]
    core = flw.basins(idxs=np.array(outlets)) > 0
    own_ha, core_ha = float(own.sum() * cell_ha), float(core.sum() * cell_ha)
    touches_edge = bool(core[0, :].any() or core[-1, :].any() or core[:, 0].any() or core[:, -1].any())
    if touches_edge:
        warnings.append(f"The spring sits on a stream whose catchment reaches beyond the {WINDOW_M / 1000:.1f} km map window, so the "
                        "surface catchment shown is only its nearby part. Check the coordinate: most springs are on a slope, not in a channel.")
    if given_elevation is not None and abs(given_elevation - z_s) > 50:
        warnings.append(f"The elevation given ({given_elevation:.0f} m) differs from the map ({z_s:.0f} m) by {abs(given_elevation - z_s):.0f} m. "
                        "The coordinate may be off; the zone is drawn from the map point.")

    # 2. search area
    band = valid & (z >= z_s - BELOW_TOLERANCE_M) & (z <= z_s + HEIGHT_ABOVE_M) & (dist <= MAX_DISTANCE_M)
    above = z >= z_s + 5
    cells_per_m = 1 / min(dx, dy)
    ridge = binary_dilation(core, iterations=max(1, round(RIDGE_MARGIN_M * cells_per_m))) & above
    wide = binary_dilation(core, iterations=max(1, round(WIDE_MARGIN_M * cells_per_m))) & above
    dip_dir, dip_angle = _number(field.get("dip_direction_deg")), _number(field.get("dip_angle_deg"))
    dip_sector = np.zeros(z.shape, bool)
    if dip_dir is not None and (dip_angle is None or dip_angle >= MIN_DIP_DEG):
        up_dip = (dip_dir + 180) % 360
        off = np.abs((bearing - up_dip + 180) % 360 - 180)
        dip_sector = (off <= DIP_SECTOR_DEG) & above
        rationale.append(f"The rock layers tilt down towards {dip_dir:.0f} degrees, so water can reach the spring from up-dip "
                         f"(towards {up_dip:.0f} degrees), even beyond the ridge; that direction was searched as well.")
    elif dip_dir is not None:
        rationale.append(f"The rock layers are nearly flat ({dip_angle:g} degrees), so their tilt was not used to extend the search.")

    # 3. recharge potential
    factors = load_factors()
    gy, gx = np.gradient(np.where(valid, z, z_s), dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    scores, used = {}, []
    vec_class = np.vectorize(lambda d: factors["slope"]["classes"][slope_class(d)])
    scores["slope"] = vec_class(slope)
    used.append("slope")

    land = np.zeros(z.shape, np.int16)
    wc, wt = mod.read_window(layers.wc, lon, lat, WINDOW_M + 100) if layers.wc else (None, None)
    if wc is not None:
        rr = np.clip(((ys - wt.f) / wt.e).astype(int), 0, wc.shape[0] - 1)
        cc = np.clip(((xs - wt.c) / wt.a).astype(int), 0, wc.shape[1] - 1)
        land = wc[rr, cc].astype(np.int16)
        lc = factors["land_cover"]["classes"]
        scores["land_cover"] = np.vectorize(lambda code: lc.get(WORLDCOVER.get(int(code), ""), 0.5))(land)
        used.append("land_cover")
    else:
        warnings.append("No land-cover map covers this location, so land cover was left out of the recharge potential.")

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True).transform
    to_lonlat = Transformer.from_crs("EPSG:32644", "EPSG:4326", always_xy=True).transform
    ux, uy = to_utm(xs.ravel(), ys.ravel())
    cell_points = shapely_points(ux, uy)
    window_utm = box(ux.min() - 200, uy.min() - 200, ux.max() + 200, uy.max() + 200)
    ngdr = layers.ngdr
    rock = np.full(z.shape, "", dtype=object)
    unit_names = np.full(z.shape, "", dtype=object)
    faults_fc = {"type": "FeatureCollection", "features": []}
    fault_cells = np.zeros(z.shape, bool)
    struct_lines = []
    geology = None
    if getattr(ngdr, "ok", False):
        hits = ngdr.unit_tree.query(window_utm, predicate="intersects")
        import shapely
        for i in hits:
            geom, props = ngdr.units[i]
            inside = shapely.contains_xy(geom, ux, uy).reshape(z.shape) & (rock == "")
            if inside.any():
                text = ngdr._clean(props.get("lithologic")).rstrip(".")
                classes = rock_classes(text)
                rock[inside] = classes[0] if len(classes) == 1 else f"Mixed ({', '.join(classes)})"
                unit_names[inside] = text.capitalize() or "Unnamed unit"
        fault_ids = list(ngdr.fault_tree.query(window_utm.buffer(600)))
        fault_geoms = [ngdr.faults[i][0] for i in fault_ids]
        fault_props = [{"name": ngdr._clean(ngdr.faults[i][1].get("fault_name")) or "Unnamed fault",
                        "type": ngdr._clean(ngdr.faults[i][1].get("fault_type")) or "Fault"} for i in fault_ids]
        faults_fc = _lines_in_window(fault_geoms, to_lonlat, window_utm, fault_props)
        if faults_fc["features"]:
            fault_cells = rasterio.features.rasterize([(f["geometry"], 1) for f in faults_fc["features"]], out_shape=z.shape,
                                                      transform=t, all_touched=True, dtype="uint8").astype(bool)
        struct_lines += fault_geoms
    if (rock != "").sum() > 0.5 * rock.size:
        rk = factors["rock"]["classes"]

        def rock_score(label):  # a mixed unit scores the mean of its rocks
            names = label[7:-1].split(", ") if label.startswith("Mixed (") else [label]
            return statistics.fmean(rk.get(n, rk.get("Other", 0.5)) for n in names)
        scores["rock"] = np.vectorize(rock_score)(np.where(rock == "", "Other", rock))
        used.append("rock")
        spring_rock = rock[row, col] or "Other"
        nearest = None
        if getattr(ngdr, "ok", False):
            f = ngdr.features(lon, lat)
            nearest = f.get("distance_to_gsi_fault_m")
            geology = {"rock_class": spring_rock, "unit": unit_names[row, col] or f.get("gsi_lithology", ""),
                       "nearest_fault_m": None if nearest is None else round(float(nearest)),
                       "nearest_fault_name": f.get("gsi_nearest_fault_name") or f.get("gsi_nearest_fault_type") or ""}
    else:
        warnings.append("This location is outside the GSI geology map used here (Uttarakhand only), so rock type and mapped faults "
                        "were left out. Record the rock at the outlet and the tilt of the layers in the field.")

    lineaments_fc = {"type": "FeatureCollection", "features": []}
    local = layers.local
    if getattr(local, "lines", None) is not None:
        line_ids = list(local.tree.query(window_utm.buffer(600)))
        line_geoms = [local.lines[i] for i in line_ids]
        lineaments_fc = _lines_in_window(line_geoms, to_lonlat, window_utm, [{"type": "DEM lineament (candidate)"}] * len(line_geoms))
        struct_lines += line_geoms
    if struct_lines:
        tree = STRtree(struct_lines)
        _, near = tree.query_nearest(cell_points, return_distance=True, all_matches=False)
        struct_dist = near.reshape(z.shape)
        st = factors["structure"]["classes"]
        scores["structure"] = np.vectorize(lambda d: st[structure_class(d)])(struct_dist)
        used.append("structure")
    else:
        struct_dist = np.full(z.shape, np.inf)
        warnings.append("No faults or lineaments were found near this spring, so fractures were left out of the recharge potential.")

    total_weight = sum(factors[f]["weight"] for f in used)
    potential = sum(scores[f] * factors[f]["weight"] for f in used) / total_weight
    water = land == 80

    # 4. size
    target = target_area(field)
    priority = potential * (0.5 + 0.5 * np.exp(-dist / DISTANCE_SCALE_M))
    priority = np.where(core, priority, priority * 0.9)
    near_spring = dist <= NEAR_SPRING_M
    stream_block = stream & ~near_spring
    fault_block = fault_cells & ~near_spring

    # 5. zones: small and likely may not cross a mapped fault; large may
    base = band & ~water & ~stream_block
    allowed_likely = base & ~fault_block & (core | ridge | dip_sector)
    allowed_large = base & (core | wide | dip_sector)
    n_small, n_likely, n_large = (max(1, math.ceil(target[k] / cell_ha)) for k in ("low", "mid", "high"))
    order = _grow((row, col), allowed_likely, priority, n_likely)
    order_large = _grow((row, col), allowed_large, priority, n_large, start=order)
    masks = {}
    for scenario, cells in (("small", order[:n_small]), ("likely", order), ("large", order_large)):
        m = np.zeros(z.shape, bool)
        rows_, cols_ = zip(*cells)
        m[list(rows_), list(cols_)] = True
        masks[scenario] = m
    limited = len(order) < n_likely
    if limited:
        warnings.append(f"The likely zone stopped at {len(order) * cell_ha:.1f} ha, short of the {target['mid']:.1f} ha target: the land "
                        "above the spring on this side of the ridge, streams and faults ran out. The real recharge area may lie beyond "
                        "the ridge; the tilt of the rock layers (dip direction) would show where.")
    smooth = abs(t.a) * 0.6
    zones = []
    zone_geoms = {}
    for scenario in ("small", "likely", "large"):
        area = float(masks[scenario].sum() * cell_ha)
        feature = _mask_to_feature(masks[scenario], t, {"scenario": scenario, "area_ha": round(area, 2)}, smooth)
        if feature:
            zones.append({"scenario": scenario, "area_ha": round(area, 2), "geojson": feature})
            zone_geoms[scenario] = shape(feature["geometry"])
    catchment_feature = _mask_to_feature(core, t, {"area_ha": round(core_ha, 2)}, smooth)
    catchment_geom = shape(catchment_feature["geometry"]) if catchment_feature else None

    # summary of the likely zone
    likely = masks["likely"]
    codes, counts = np.unique(land[likely], return_counts=True)
    land_pct = {WORLDCOVER.get(int(c), "No data"): round(100 * n / likely.sum(), 1) for c, n in zip(codes, counts) if c}
    rock_units = sorted({u for u in unit_names[likely] if u})
    crosses_fault = bool((fault_cells & masks["large"]).any())
    zone_summary = {"mean_potential": round(float(potential[likely].mean()), 2),
                    "mean_slope_deg": round(float(slope[likely].mean()), 1),
                    "elevation_range_m": [round(float(z[likely].min())), round(float(z[likely].max()))],
                    "land_cover_pct": dict(sorted(land_pct.items(), key=lambda kv: -kv[1])),
                    "rock_units": rock_units[:6], "crosses_fault": crosses_fault}

    # best spots for recharge works inside the likely zone
    spots = []
    candidates = np.argwhere(likely & (land != 50) & ~water)
    ranked = sorted(candidates.tolist(), key=lambda rc: -potential[rc[0], rc[1]])
    for r, c in ranked:
        if len(spots) == 3:
            break
        p = (float(ys[r, c]), float(xs[r, c]))
        if any(math.hypot((p[0] - s["latitude"]) * m_lat, (p[1] - s["longitude"]) * m_lon) < SPOT_SEPARATION_M for s in spots):
            continue
        why = [f"{slope[r, c]:.0f} degree slope"]
        if land[r, c]:
            why.insert(0, WORLDCOVER.get(int(land[r, c]), "").lower())
        if rock[r, c]:
            why.append(f"{rock[r, c].lower()} rock" if not rock[r, c].startswith("Mixed") else "mixed rock")
        if np.isfinite(struct_dist[r, c]):
            why.append(f"{struct_dist[r, c]:.0f} m from a fault or lineament")
        spots.append({"latitude": round(p[0], 6), "longitude": round(p[1], 6), "elevation_m": round(float(z[r, c])),
                      "potential": round(float(potential[r, c]), 2), "reason": ", ".join(w for w in why if w).capitalize()})

    # recharge-potential picture for the map
    show = band & ~water
    level = np.clip((potential * len(LEGEND)).astype(int), 0, len(LEGEND) - 1)
    rgba = np.zeros(z.shape + (4,), np.uint8)
    for i, (_, color) in enumerate(LEGEND):
        rgba[show & (level == i)] = color
    south, north = t.f + z.shape[0] * t.e, t.f
    west, east = t.c, t.c + z.shape[1] * t.a
    overlay = {"image": _png(rgba), "bounds": [[south, west], [north, east]],
               "legend": [{"label": label, "color": "#%02x%02x%02x" % color[:3]} for label, color in LEGEND]}

    streams_fc = {"type": "FeatureCollection", "features": []}
    try:
        feats = flw.streams(mask=upa >= STREAM_DISPLAY_KM2)
        streams_fc["features"] = [{"type": "Feature", "geometry": f["geometry"],
                                   "properties": {"order": int(f["properties"].get("strord", 1) or 1)}} for f in feats]
    except Exception as error:  # streams are display only
        warnings.append(f"Streams could not be drawn: {error}")

    # words
    likely_ha = zones[1]["area_ha"] if len(zones) > 1 else 0
    rationale[:0] = [
        f"The land that drains to the spring on the surface (its surface catchment) is {core_ha:.1f} ha"
        + (" or more" if touches_edge else "") + f", allowing 30 m for GPS and map error ({own_ha:.1f} ha drains to the exact map cell). "
        "Rain soaking in here can feed the spring, but the rocks decide the real recharge area.",
        f"The likely recharge zone is {likely_ha:.1f} ha (small {zones[0]['area_ha']:.1f} ha, large {zones[-1]['area_ha']:.1f} ha). "
        + target["basis"],
        f"It was grown uphill from the spring, between its level ({z_s:.0f} m) and {HEIGHT_ABOVE_M} m above it, taking first the "
        "cells most likely to soak up rain (" + ", ".join(factors[f]["name"].lower() for f in used) + ") and those closest to the spring. "
        "It does not cross streams, and the small and likely zones do not cross mapped faults.",
    ]
    forest = sum(v for k, v in land_pct.items() if k in ("Tree cover", "Shrubland", "Grassland"))
    disturbed = sum(v for k, v in land_pct.items() if k in ("Built-up", "Cropland", "Bare / sparse vegetation"))
    rationale.append(f"In the likely zone: {forest:.0f}% forest, shrub or grass and {disturbed:.0f}% built-up, farmed or bare land; "
                     f"mean slope {zone_summary['mean_slope_deg']:.0f} degrees; land from {zone_summary['elevation_range_m'][0]} to "
                     f"{zone_summary['elevation_range_m'][1]} m.")
    if crosses_fault:
        rationale.append("A mapped GSI fault crosses the large zone. Faults can carry water to the spring or cut it off; a geologist "
                         "should check which side feeds it.")
    if spots:
        rationale.append(f"The best places for recharge works (trenches, pits, plantation) are marked: {spots[0]['reason'].lower()}.")
    if target["kind"] == "default":
        missing.append({"id": "monsoon_flow_lpm", "indicator": "Monsoon flow", "needs": "One bucket reading in the monsoon sizes the zone for this spring."})
    elif target["kind"] == "lean flow":
        missing.append({"id": "monsoon_flow_lpm", "indicator": "Monsoon flow", "needs": "A monsoon reading sizes the zone better than the lean-season flow."})
    if dip_dir is None:
        missing.append({"id": "dip_direction_deg", "indicator": "Rock tilt (dip direction and angle)",
                        "needs": "A compass reading of the rock layers near the outlet shows whether the recharge area lies beyond the ridge."})
    missing.append({"id": "field_walk", "indicator": "Field check", "needs": "Walk the likely zone with a geologist before spending money on works."})
    confidence = "Medium" if target["kind"] == "monsoon flow" and dip_dir is not None and "rock" in used else "Low"

    result = {
        "spring_cell": {"latitude": round(float(ys[row, col]), 6), "longitude": round(float(xs[row, col]), 6), "elevation_m": round(z_s),
                        "moved_m": 0, "note": "The 30 m map cell at the given coordinate."},
        "surface_catchment": {"area_ha": round(core_ha, 2), "geojson": catchment_feature},
        "target_area_ha": {"low": target["low"], "mid": target["mid"], "high": target["high"], "basis": target["basis"]},
        "height_band_m": {"min": round(z_s - BELOW_TOLERANCE_M), "max": round(z_s + HEIGHT_ABOVE_M)},
        "zones": zones,
        "potential_overlay": overlay,
        "factors": [{"id": f, "name": factors[f]["name"], "weight_pct": round(100 * factors[f]["weight"] / total_weight),
                     "how": factors[f]["why"]} for f in used],
        "zone_summary": zone_summary,
        "geology": geology,
        "faults": faults_fc,
        "lineaments": lineaments_fc,
        "streams": streams_fc,
        "recharge_spots": spots,
    }
    output = {
        "module": "B", "title": "Springshed and recharge zone", "version": "v1 draft",
        "spring": {"name": name, "latitude": lat, "longitude": lon, "elevation_m": given_elevation if given_elevation is not None else round(z_s)},
        "status": "provisional", "result": result, "confidence": confidence,
        "rationale": rationale, "missing_inputs": missing, "warnings": warnings,
        "report_markdown": report_markdown(name, lat, lon, result, rationale, warnings),
        "_zones": {**zone_geoms, "catchment": catchment_geom, "dem": (z, t), "spring_elevation_m": z_s},
    }
    return output


def report_markdown(name, lat, lon, result, rationale, warnings):
    zones = {z["scenario"]: z["area_ha"] for z in result["zones"]}
    lines = [f"# Springshed and recharge zone: {name}", "",
             f"Location {lat:.5f}, {lon:.5f}; map elevation {result['spring_cell']['elevation_m']} m.", "",
             "| | Area (ha) |", "|---|---|",
             f"| Surface catchment (allowing 30 m GPS error) | {result['surface_catchment']['area_ha']:.1f} |",
             *(f"| {s.capitalize()} recharge zone | {zones[s]:.1f} |" for s in ("small", "likely", "large") if s in zones), "",
             "## Why", *(f"- {r}" for r in rationale), ""]
    if result["recharge_spots"]:
        lines += ["## Best places for recharge works", *(f"- {s['latitude']:.5f}, {s['longitude']:.5f} ({s['elevation_m']} m): {s['reason']}"
                                                          for s in result["recharge_spots"]), ""]
    if warnings:
        lines += ["## Notes", *(f"- {w}" for w in warnings), ""]
    lines += ["A first estimate from maps (Module B v1 draft). Walk the zone with a geologist before spending money on works."]
    return "\n".join(lines)


def public(output):
    """The output without the in-memory geometries (safe to turn into JSON)."""
    return {k: v for k, v in output.items() if not k.startswith("_")}


def main():
    import module_a_vulnerability as module_a
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--elevation", type=float)
    parser.add_argument("--name")
    parser.add_argument("--monsoon-flow-lpm", type=float)
    parser.add_argument("--lean-flow-lpm", type=float)
    parser.add_argument("--dip-direction", type=float)
    parser.add_argument("--dip-angle", type=float)
    parser.add_argument("--geojson", help="write the zones and catchment to this GeoJSON file")
    parser.add_argument("--cache", default=os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
    parser.add_argument("--local-layers", default=os.environ.get("SPRING_LOCAL_LAYERS", str(ROOT / ".local_layers")))
    args = parser.parse_args()
    session = module_a.LayerSession(args.cache, args.local_layers)
    field = {"monsoon_flow_lpm": args.monsoon_flow_lpm, "lean_flow_lpm": args.lean_flow_lpm,
             "dip_direction_deg": args.dip_direction, "dip_angle_deg": args.dip_angle}
    output = delineate({"spring": {"name": args.name, "latitude": args.lat, "longitude": args.lon, "elevation_m": args.elevation},
                        "field": field}, session)
    print(output["report_markdown"])
    if args.geojson and output["result"]:
        r = output["result"]
        features = [z["geojson"] for z in r["zones"]] + ([r["surface_catchment"]["geojson"]] if r["surface_catchment"]["geojson"] else [])
        Path(args.geojson).write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
        print(f"Saved {args.geojson}")


if __name__ == "__main__":
    main()

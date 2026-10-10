"""Extract candidate lineaments from the Copernicus 30 m DEM for the spring tiles.

Method (the usual automatic approach, as in PCI Geomatica LINE):
1. Smooth the DEM (Gaussian, sigma 1.5 cells) to suppress single-cell noise.
2. Shade it from four light directions (0, 45, 90, 135 degrees, sun 30 degrees up).
3. Find sharp light/dark edges in each shaded image (Canny, sigma 3; edges start in the top 5% of
   gradients and extend through cells above about the median)
   and combine them.
4. Keep only straight edge runs of at least 30 cells (~0.9 km) with a probabilistic
   Hough transform, in 600-cell blocks.

The result is a set of straight terrain lines. Many are faults, joints or fracture-
controlled valleys, but some are ridges or valleys with no structural cause. Treat
them as unvalidated candidates until checked against GSI fault maps or field work.

Usage: python scripts/extract_dem_lineaments.py [--cache DIR]
Reads DEM tiles from <cache>/dem (downloaded by build_spring_features.py) and the
spring coordinates from the processed feature table; writes
data/02_processed/lineaments/dem_lineament_candidates_v1.geojson.
"""

import argparse
import csv
import json
import math
import os
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter
from skimage.feature import canny
from skimage.transform import probabilistic_hough_line


ROOT = Path(__file__).resolve().parents[1]
FEATURES_CSV = ROOT / "data" / "02_processed" / "spring_features" / "spring_features_v1.csv"
OUT_DIR = ROOT / "data" / "02_processed" / "lineaments"
OUT_FILE = OUT_DIR / "dem_lineament_candidates_v1.geojson"

SMOOTH_SIGMA = 1.5
SUN_AZIMUTHS = (0, 45, 90, 135)
SUN_ALTITUDE = 30
CANNY_SIGMA = 3
CANNY_HIGH_QUANTILE = 0.95
CANNY_LOW_QUANTILE = 0.475
MIN_LENGTH_CELLS = 30
MAX_GAP_CELLS = 2
HOUGH_THRESHOLD = 10
BLOCK = 600


def tile_segments(path):
    with rasterio.open(path) as ds:
        z = ds.read(1).astype("float32")
        transform = ds.transform
    z[z <= -1000] = np.nan
    if np.isnan(z).all():
        return []
    z = np.where(np.isnan(z), np.nanmean(z), z)
    lat = transform.f + transform.e * z.shape[0] / 2
    m_lat = 111132.92 - 559.82 * math.cos(2 * math.radians(lat))
    m_lon = 111412.84 * math.cos(math.radians(lat))
    dx, dy = transform.a * m_lon, -transform.e * m_lat
    smooth = gaussian_filter(z, SMOOTH_SIGMA)
    gy, gx = np.gradient(smooth, dy, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    alt = math.radians(SUN_ALTITUDE)
    edges = np.zeros(z.shape, bool)
    for azimuth in SUN_AZIMUTHS:
        shade = math.sin(alt) * np.cos(slope) + math.cos(alt) * np.sin(slope) * np.cos(math.radians(azimuth) - aspect)
        edges |= canny(shade, sigma=CANNY_SIGMA, low_threshold=CANNY_LOW_QUANTILE,
                       high_threshold=CANNY_HIGH_QUANTILE, use_quantiles=True)
    segments = []
    for r in range(0, z.shape[0], BLOCK):
        for c in range(0, z.shape[1], BLOCK):
            lines = probabilistic_hough_line(edges[r:r + BLOCK, c:c + BLOCK], threshold=HOUGH_THRESHOLD,
                                             line_length=MIN_LENGTH_CELLS, line_gap=MAX_GAP_CELLS, rng=0)
            for (x0, y0), (x1, y1) in lines:
                lon0, lat0 = transform * (c + x0 + 0.5, r + y0 + 0.5)
                lon1, lat1 = transform * (c + x1 + 0.5, r + y1 + 0.5)
                length = math.hypot((lon1 - lon0) * m_lon, (lat1 - lat0) * m_lat)
                bearing = math.degrees(math.atan2((lon1 - lon0) * m_lon, (lat1 - lat0) * m_lat)) % 180
                segments.append(((lon0, lat0), (lon1, lat1), length, bearing))
    return segments


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", default=os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
    args = parser.parse_args()
    with FEATURES_CSV.open(encoding="utf-8", newline="") as handle:
        cells = {(math.floor(float(r["latitude_dd"])), math.floor(float(r["longitude_dd"])))
                 for r in csv.DictReader(handle) if r["coordinate_status"] == "ok"}
    features, tiles = [], []
    for lat, lon in sorted(cells):
        name = f"Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM"
        path = Path(args.cache) / "dem" / f"{name}.tif"
        segments = tile_segments(path)
        tiles.append({"tile": name, "segments": len(segments)})
        print(f"{name}: {len(segments)} segments")
        for start, end, length, bearing in segments:
            features.append({
                "type": "Feature",
                "properties": {"id": f"LIN-{len(features) + 1:06d}", "length_m": round(length), "bearing_deg": round(bearing),
                               "source_tile": name},
                "geometry": {"type": "LineString", "coordinates": [[round(v, 6) for v in start], [round(v, 6) for v in end]]},
            })
    collection = {
        "type": "FeatureCollection",
        "name": "dem_lineament_candidates_v1",
        "metadata": {
            "built": date.today().isoformat(),
            "dem": "Copernicus DEM GLO-30 (1 arc-second), tiles containing spring coordinates",
            "method": "Gaussian smoothing, 4-direction shaded relief, Canny edges, probabilistic Hough transform",
            "parameters": {"smooth_sigma_cells": SMOOTH_SIGMA, "sun_azimuths_deg": SUN_AZIMUTHS, "sun_altitude_deg": SUN_ALTITUDE,
                           "canny_sigma": CANNY_SIGMA, "canny_high_quantile": CANNY_HIGH_QUANTILE, "canny_low_quantile": CANNY_LOW_QUANTILE,
                           "min_length_cells": MIN_LENGTH_CELLS, "max_gap_cells": MAX_GAP_CELLS, "block_cells": BLOCK},
            "tiles": tiles,
            "caveat": "Unvalidated candidates. Includes structural lineaments and non-structural ridge/valley lines.",
        },
        "features": features,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(collection, separators=(",", ":")), encoding="utf-8")
    print(f"{len(features)} segments written to {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

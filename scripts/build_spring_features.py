"""Build the processed per-spring feature table from the common file and public layers.

Input:  data/01_staged/common/csv/spring_records_common_v1.csv
Output: data/02_processed/spring_features/spring_features_v1.csv (+ data dictionary,
        coverage table and metadata JSON)

Public layers (downloaded once into a local cache, never committed):
- Copernicus DEM GLO-30 (AWS open data, 1-arcsecond tiles)
- ESA WorldCover 10 m 2021 v200 (AWS open data, 3-degree tiles)
- CHIRPS precipitation, annual and monthly 2018-2025, as republished by FAO WaPOR v3 (L1-PCP-A/M, ~5 km)
- FAO WaPOR v3 reference evapotranspiration, annual 2018-2025 (L1-RET-A, ~30 km)
- FAO/IIASA Harmonized World Soil Database v2.0 (30 arc-second raster + database tables exported to CSV)

Layers downloaded by hand (logins or manual export), read from --local-layers DIR:
- Bhoonidhi/*.zip      NRSC CartoDEM v3 30 m tiles, as downloaded from Bhoonidhi
- IMD/*.nc             IMD 0.25 degree daily gridded rainfall (one calendar year per file; 2021-2025 used)
- SoilGrids/<prop>_<depth>_mean.tif   ISRIC SoilGrids 2.0 exports (clay, silt, sand, bdod, ocd, cfvo;
                       depths 0-5, 5-15 and 15-30 cm)
DEM lineament candidates come from scripts/extract_dem_lineaments.py (--lineaments FILE).
DEM hydrology (drainage area, wetness index, distance to stream) comes from scripts/spring_hydrology.py.
GSI NGDR (Bhukosh) Uttarakhand lithology polygons, fault lines and fold axes are read from
data/00_raw/ngdr_geology/ (committed; staged attribute tables in data/01_staged/ngdr_geology/).

Rules: staged source text is never edited. Parsed numbers are new columns with
a parse note. Unit conversions are new columns named *_converted. Layer values
describe the pixel or buffer around the coordinate as given; they are not field
measurements. Usage: python scripts/build_spring_features.py [--cache DIR]
"""

import argparse
import csv
import json
import math
import os
import re
import statistics
import subprocess
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.windows import from_bounds
from pyproj import Transformer
from shapely import STRtree, LineString, Point
from shapely.geometry import shape
from shapely import transform as shapely_transform

from spring_hydrology import STREAM_THRESHOLD_KM2, hydrology_features


ROOT = Path(__file__).resolve().parents[1]
COMMON_CSV = ROOT / "data" / "01_staged" / "common" / "csv" / "spring_records_common_v1.csv"
OUT_DIR = ROOT / "data" / "02_processed" / "spring_features"

DEM_URL = "https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"
WC_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
WAPOR_URL = "https://storage.googleapis.com/fao-gismgr-wapor-3-data/DATA/WAPOR-3/MAPSET/{code}/WAPOR-3.{code}.{period}.tif"
HWSD_URLS = [
    "https://s3.eu-west-1.amazonaws.com/data.gaezdev.aws.fao.org/HWSD/HWSD2_RASTER.zip",
    "https://s3.eu-west-1.amazonaws.com/data.gaezdev.aws.fao.org/HWSD/HWSD2_DB.zip",
]
YEARS = list(range(2018, 2026))
NGDR_DIR = ROOT / "data" / "00_raw" / "ngdr_geology"
NGDR_LITHOLOGY = NGDR_DIR / "lithology" / "LITHOLOGY_STATE_UTTARAKHAND.geojson"
NGDR_FAULTS = NGDR_DIR / "faults" / "FAULT_STATE_UTTARAKHAND.geojson"
NGDR_FOLDS = NGDR_DIR / "folds" / "FOLD_STATE_UTTARAKHAND.geojson"
LINEAMENTS_FILE = ROOT / "data" / "02_processed" / "lineaments" / "dem_lineament_candidates_v1.geojson"

# SoilGrids exports: (property, column stem, unit, divisor to reach the unit, description). 0 = no data.
SOILGRID_DEPTHS = [("0-5cm", "0_5cm"), ("5-15cm", "5_15cm"), ("15-30cm", "15_30cm")]
SOILGRID_PROPERTIES = [
    ("clay", "sg_clay", "%", 10, "Clay (g/kg / 10)"),
    ("silt", "sg_silt", "%", 10, "Silt (g/kg / 10)"),
    ("sand", "sg_sand", "%", 10, "Sand (g/kg / 10)"),
    ("cfvo", "sg_coarse_fragments", "%", 10, "Coarse fragments, volume share (cm3/dm3 / 10)"),
    ("bdod", "sg_bulk_density", "g/cm3", 100, "Bulk density of the fine earth (cg/cm3 / 100)"),
    ("ocd", "sg_org_carbon_density", "kg/m3", 10, "Organic carbon density (hg/m3 / 10)"),
]
SOILGRIDS = [(f"{prop}_{depth}_mean", f"{stem}_{label}_{unit.replace('%', 'pct').replace('/', '_')}", divisor)
             for prop, stem, unit, divisor, _ in SOILGRID_PROPERTIES for depth, label in SOILGRID_DEPTHS]
IMD_MONSOON_MONTHS = (6, 9)

# Study region: Uttarakhand and Himachal Pradesh springs in the common file.
REGION = {"lat_min": 28.5, "lat_max": 33.5, "lon_min": 75.5, "lon_max": 81.5}

WORLDCOVER_CLASSES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
    60: "Bare / sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
    90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen",
}
WC_SHARE_COLUMNS = {10: "tree", 20: "shrub", 30: "grass", 40: "cropland", 50: "built", 60: "bare", 80: "water"}

DISTRICT_FIXES = {
    "nanital": "Nainital", "nainital": "Nainital", "tehri garhwal": "Tehri Garhwal", "tehri-garhwal": "Tehri Garhwal",
    "pauri garhwal": "Pauri Garhwal", "pauri": "Pauri Garhwal",
}

# Coordinates corrected where the error and the fix are both certain. The staged value is not edited;
# the correction is applied here and named in coordinate_correction.
COORDINATE_FIXES = {
    "ATL-SPR-0006": (29.44050, None, "latitude 26.44050 read as 29.44050 (typing slip: Sunkiya -2, ATL-SPR-0007, is at 29.44343; "
                                     "the DEM at the corrected point is 2,049 m against 2,035 m in the source)"),
    "ATL-SPR-0818": (None, 80.029444, "longitude repeated the latitude; taken from HIM-SPR-0204 (Malla Naula, Khatigaon), which has the "
                                      "same latitude 29.59992 and the same elevation 1,279 m"),
}
COORDINATE_NOTES = {
    "ATL-SPR-0792": "latitude repeats the longitude (80.05146); probably the Gunagad spring listed as ATL-SPR-0791 (same longitude, "
                    "1,613 m against 1,612 m), but the latitude cannot be recovered with certainty",
}
ELEVATION_GAP_M = 150
ELEVATION_MATCH_TOLERANCE_M = 25
ELEVATION_SEARCH_M = 2000

NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


# --------------------------------------------------------------------------- helpers
def fmt(value, digits=2):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return f"{float(value):.{digits}f}"


def download(url, path):
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(url) as response, tmp.open("wb") as handle:
        while chunk := response.read(1 << 20):
            handle.write(chunk)
    tmp.rename(path)


def to_float(text):
    try:
        return float(str(text).replace(",", "").strip())
    except ValueError:
        return None


def parse_numbers(text):
    """Return (low, high, note) from free text such as '~2-8 lpm dry; 15-25+ lpm wet'."""
    text = (text or "").strip()
    if not text:
        return None, None, ""
    numbers = [float(n) for n in NUMBER.findall(text.replace(",", ""))]
    if not numbers:
        return None, None, "no number in source text"
    lowered = text.lower()
    if len(numbers) == 1:
        note = "single value" if re.fullmatch(r"~?\s*\d+(\.\d+)?\s*(ha|lpm|l/min|mm)?", lowered) else "single number in text"
    elif any(word in lowered for word in ("dry", "wet", "monsoon", "season")):
        note = "multi-season text: low = lowest number, high = highest number"
    else:
        note = "range: low and high numbers in text"
    if "~" in text or "approx" in lowered:
        note += "; approximate in source"
    return min(numbers), max(numbers), note


def metres_per_degree(lat):
    lat_r = math.radians(lat)
    return 111132.92 - 559.82 * math.cos(2 * lat_r), 111412.84 * math.cos(lat_r)


def read_window(paths, lon, lat, radius_m):
    """Mosaic the tiles needed to cover a square of +/- radius_m around the point."""
    m_lat, m_lon = metres_per_degree(lat)
    dlat, dlon = radius_m / m_lat, radius_m / m_lon
    bounds = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    datasets = [ds for ds in paths if not (ds.bounds.right < bounds[0] or ds.bounds.left > bounds[2]
                                           or ds.bounds.top < bounds[1] or ds.bounds.bottom > bounds[3])]
    if not datasets:
        return None, None
    if len(datasets) == 1:
        ds = datasets[0]
        window = from_bounds(*bounds, transform=ds.transform).round_offsets().round_lengths()
        data = ds.read(1, window=window, boundless=True, fill_value=ds.nodata if ds.nodata is not None else 0)
        return data, ds.window_transform(window)
    data, transform = merge(datasets, bounds=bounds)
    return data[0], transform


def distance_grid(shape, transform, lon, lat):
    rows, cols = np.indices(shape)
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e
    m_lat, m_lon = metres_per_degree(lat)
    return np.hypot((xs - lon) * m_lon, (ys - lat) * m_lat)


def centre_index(transform, lon, lat):
    col = int((lon - transform.c) / transform.a)
    row = int((lat - transform.f) / transform.e)
    return row, col


# --------------------------------------------------------------------------- layers
def dem_tiles_for(points, cache):
    cells = set()
    for lat, lon in points:
        for dy in (-0.02, 0, 0.02):
            for dx in (-0.02, 0, 0.02):
                cells.add((math.floor(lat + dy), math.floor(lon + dx)))
    paths = []
    for la, lo in sorted(cells):
        name = f"Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM"
        path = cache / "dem" / f"{name}.tif"
        try:
            download(DEM_URL.format(name=name), path)
            paths.append(path)
        except Exception as error:  # ocean/no-data tiles do not exist
            print(f"DEM tile {name} unavailable: {error}")
    return paths


def worldcover_tiles_for(points, cache):
    tiles = set()
    for lat, lon in points:
        for dy in (-0.01, 0, 0.01):
            for dx in (-0.01, 0, 0.01):
                la, lo = math.floor((lat + dy) / 3) * 3, math.floor((lon + dx) / 3) * 3
                tiles.add(f"N{la:02d}E{lo:03d}")
    paths = []
    for tile in sorted(tiles):
        path = cache / "worldcover" / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        download(WC_URL.format(tile=tile), path)
        paths.append(path)
    return paths


def dem_features(dem_sets, lon, lat):
    data, transform = read_window(dem_sets, lon, lat, 1100)
    if data is None:
        return {}
    data = data.astype("float64")
    data[data <= -1000] = np.nan
    row, col = centre_index(transform, lon, lat)
    if not (1 <= row < data.shape[0] - 1 and 1 <= col < data.shape[1] - 1):
        return {}
    m_lat, m_lon = metres_per_degree(lat)
    dx, dy = abs(transform.a) * m_lon, abs(transform.e) * m_lat
    gy, gx = np.gradient(data, dy, dx)  # rows run north to south
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    # Aspect: direction the slope faces, degrees clockwise from north.
    aspect = (np.degrees(np.arctan2(-gx, gy)) + 360) % 360
    dist = distance_grid(data.shape, transform, lon, lat)
    elev = data[row, col]
    within_1km = data[dist <= 1000]
    within_300 = data[dist <= 300]
    slope_500 = slope[dist <= 500]
    a = aspect[row, col]
    classes = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    flat = slope[row, col] < 2
    return {
        "dem_elevation_m": elev,
        "dem_slope_deg": slope[row, col],
        "dem_aspect_deg": None if flat else a,
        "dem_aspect_class": "Flat" if flat else classes[int(((a + 22.5) % 360) // 45)],
        "dem_mean_slope_500m_deg": np.nanmean(slope_500),
        "dem_relief_1km_m": np.nanmax(within_1km) - np.nanmin(within_1km),
        "dem_upslope_relief_1km_m": np.nanmax(within_1km) - elev,
        "dem_tpi_300m_m": elev - np.nanmean(within_300),
    }


def elevation_match_distance(dem_sets, lon, lat, target):
    """Distance to the nearest DEM cell whose elevation is within the tolerance of the source elevation."""
    data, transform = read_window(dem_sets, lon, lat, ELEVATION_SEARCH_M)
    if data is None:
        return None
    data = data.astype("float64")
    dist = distance_grid(data.shape, transform, lon, lat)
    hits = (np.abs(data - target) <= ELEVATION_MATCH_TOLERANCE_M) & (dist <= ELEVATION_SEARCH_M)
    return float(dist[hits].min()) if hits.any() else None


def worldcover_features(wc_sets, lon, lat):
    data, transform = read_window(wc_sets, lon, lat, 520)
    if data is None:
        return {}
    row, col = centre_index(transform, lon, lat)
    dist = distance_grid(data.shape, transform, lon, lat)
    ring = data[(dist <= 500) & (data > 0)]
    if ring.size == 0:
        return {}
    point_code = int(data[row, col])
    codes, counts = np.unique(ring, return_counts=True)
    majority = int(codes[np.argmax(counts)])
    result = {
        "wc_point_class_code": point_code,
        "wc_point_class": WORLDCOVER_CLASSES.get(point_code, ""),
        "wc_majority_500m_class": WORLDCOVER_CLASSES.get(majority, ""),
    }
    for code, name in WC_SHARE_COLUMNS.items():
        result[f"wc_share_500m_{name}_pct"] = 100.0 * float(np.sum(ring == code)) / ring.size
    return result


class WaporStack:
    """Reads one regional window per WaPOR raster, then samples points from memory."""

    def __init__(self, code, periods, scale=0.1):
        self.grids = {}
        for period in periods:
            url = "/vsicurl/" + WAPOR_URL.format(code=code, period=period)
            with rasterio.open(url) as ds:
                window = from_bounds(REGION["lon_min"], REGION["lat_min"], REGION["lon_max"], REGION["lat_max"], ds.transform)
                window = window.round_offsets().round_lengths()
                data = ds.read(1, window=window).astype("float64")
                data[data == ds.nodata] = np.nan
                self.grids[period] = (data * scale, ds.window_transform(window))

    def sample(self, period, lon, lat):
        data, transform = self.grids[period]
        row, col = centre_index(transform, lon, lat)
        if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
            return data[row, col]
        return float("nan")


class Hwsd:
    def __init__(self, cache):
        folder = cache / "hwsd"
        for url in HWSD_URLS:
            zipped = folder / url.rsplit("/", 1)[1]
            download(url, zipped)
            if not (folder / "HWSD2.bil").exists() or not (folder / "HWSD2.mdb").exists():
                subprocess.run(["unzip", "-o", "-q", str(zipped), "-d", str(folder)], check=True)
        for table in ("HWSD2_SMU", "HWSD2_LAYERS", "D_WRB4", "D_DRAINAGE", "D_TEXTURE_USDA"):
            if not (folder / f"{table}.csv").exists():
                raise FileNotFoundError(
                    f"{folder / table}.csv missing: run python scripts/export_hwsd_tables.py {folder / 'HWSD2.mdb'}"
                )
        # HWSD2.bil: 16-bit little-endian BIL grid, 43200 x 21600 cells of 30 arc-seconds from (-180, 90).
        self.raster = np.memmap(folder / "HWSD2.bil", dtype="<u2", mode="r", shape=(21600, 43200))
        self.smu = {}
        with (folder / "HWSD2_SMU.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                self.smu[str(int(float(row["HWSD2_SMU_ID"])))] = row
        self.topsoil = {}
        with (folder / "HWSD2_LAYERS.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["LAYER"] == "D1" and row["SEQUENCE"] in ("1", "1.0"):
                    self.topsoil[str(int(float(row["HWSD2_SMU_ID"])))] = row
        self.wrb = self._lookup(folder / "D_WRB4.csv", "CODE", "VALUE")
        self.drainage = self._lookup(folder / "D_DRAINAGE.csv", "CODE", "VALUE")
        self.texture = self._lookup(folder / "D_TEXTURE_USDA.csv", "CODE", "VALUE")

    @staticmethod
    def _lookup(path, key, value):
        with path.open(encoding="utf-8") as handle:
            return {row[key].strip(): row[value].strip() for row in csv.DictReader(handle)}

    def features(self, lon, lat):
        row, col = int((90 - lat) * 120), int((lon + 180) * 120)
        smu_id = int(self.raster[row, col])
        if smu_id in (0, 65535):
            return {}
        key = str(smu_id)
        smu = self.smu.get(key, {})
        top = self.topsoil.get(key, {})

        def num(row_, field):
            value = to_float(row_.get(field, ""))
            return None if value is None or value < 0 else value

        texture_code = str(int(float(top["TEXTURE_USDA"]))) if top.get("TEXTURE_USDA") not in (None, "", "None") else ""
        return {
            "soil_hwsd2_smu_id": smu_id,
            "soil_dominant_wrb": self.wrb.get(smu.get("WRB4", ""), smu.get("WRB4", "")),
            "soil_dominant_share_pct": num(smu, "SHARE"),
            "soil_drainage": self.drainage.get(smu.get("DRAINAGE", ""), smu.get("DRAINAGE", "")),
            "soil_awc_mm_per_m": num(smu, "AWC"),
            "soil_topsoil_sand_pct": num(top, "SAND"),
            "soil_topsoil_silt_pct": num(top, "SILT"),
            "soil_topsoil_clay_pct": num(top, "CLAY"),
            "soil_topsoil_texture_usda": self.texture.get(texture_code, ""),
            "soil_topsoil_coarse_fragments_pct": num(top, "COARSE"),
            "soil_topsoil_org_carbon_pct": num(top, "ORG_CARBON"),
        }


class LocalLayers:
    """Layers Rajat downloaded by hand (CartoDEM, IMD, SoilGrids) plus DEM lineament candidates."""

    def __init__(self, folder, lineaments_file):
        folder = Path(folder)
        self.found = []
        self.cartodem = [rasterio.open(f"zip://{p}!{name}") for p in sorted((folder / "Bhoonidhi").glob("*.zip"))
                         for name in self._zip_tifs(p)]
        if self.cartodem:
            self.found.append(f"CartoDEM: {len(self.cartodem)} tiles")
        self.imd = {}  # year -> (days x rows x cols array, transform)
        for path in sorted((folder / "IMD").glob("*.nc")):
            with rasterio.open(path) as ds:
                data = ds.read().astype("float64")
                year = date.fromordinal(date(1900, 12, 31).toordinal() + int(ds.tags(1)["NETCDF_DIM_TIME"])).year
                transform = ds.transform
            data[data < 0] = np.nan
            self.imd[year] = (data, transform)
        if self.imd:
            self.found.append(f"IMD: {len(self.imd)} years ({', '.join(map(str, sorted(self.imd)))})")
        self.soil = {}
        for stem, column, divisor in SOILGRIDS:
            path = folder / "SoilGrids" / f"{stem}.tif"
            if path.exists():
                with rasterio.open(path) as ds:
                    self.soil[column] = (ds.read(1).astype("float64") / divisor, ds.transform)
        if self.soil:
            self.found.append(f"SoilGrids: {len(self.soil)} layers")
        self.lines = None
        if Path(lineaments_file).exists():
            collection = json.loads(Path(lineaments_file).read_text(encoding="utf-8"))
            self.to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
            geoms = []
            for feature in collection["features"]:
                xs, ys = self.to_utm.transform(*zip(*feature["geometry"]["coordinates"]))
                geoms.append(LineString(list(zip(xs, ys))))
            self.lines = geoms
            self.tree = STRtree(geoms)
            self.found.append(f"DEM lineaments: {len(geoms)} segments")

    @staticmethod
    def _zip_tifs(path):
        import zipfile
        return [n for n in zipfile.ZipFile(path).namelist() if n.lower().endswith(".tif")]

    @staticmethod
    def _cell(transform, shape, lon, lat):
        row, col = centre_index(transform, lon, lat)
        return (row, col) if 0 <= row < shape[0] and 0 <= col < shape[1] else None

    def features(self, lon, lat):
        result = {}
        for ds in self.cartodem:
            b = ds.bounds
            if b.left <= lon < b.right and b.bottom <= lat < b.top:
                row, col = ds.index(lon, lat)
                window = rasterio.windows.Window(col - 1, row - 1, 3, 3)
                z = ds.read(1, window=window, boundless=True, fill_value=-32768).astype("float64")
                z[z <= -1000] = np.nan
                if z.shape == (3, 3) and not np.isnan(z).any():
                    m_lat, m_lon = metres_per_degree(lat)
                    dx, dy = ds.res[0] * m_lon, ds.res[1] * m_lat
                    gx = (z[1, 2] - z[1, 0]) / (2 * dx)
                    gy = (z[0, 1] - z[2, 1]) / (2 * dy)
                    result["cartodem_elevation_m"] = z[1, 1]
                    result["cartodem_slope_deg"] = math.degrees(math.atan(math.hypot(gx, gy)))
                break
        years = {}
        for year, (data, transform) in sorted(self.imd.items()):
            cell = self._cell(transform, data.shape[1:], lon, lat)
            series = data[:, cell[0], cell[1]] if cell else None
            if series is None or np.isnan(series).all():
                continue
            start = date(year, IMD_MONSOON_MONTHS[0], 1).timetuple().tm_yday - 1
            end = date(year, IMD_MONSOON_MONTHS[1], 30).timetuple().tm_yday
            total = np.nansum(series)
            years[year] = {"total": total, "monsoon": np.nansum(series[start:end]),
                           "rainy_days": int(np.sum(series >= 2.5)), "max_1day": np.nanmax(series)}
            result[f"rain_imd_{year}_mm"] = total
        if years:
            totals = [v["total"] for v in years.values()]
            mean = statistics.fmean(totals)
            result["rain_imd_mean_annual_mm"] = mean
            result["rain_imd_min_annual_mm"] = min(totals)
            result["rain_imd_max_annual_mm"] = max(totals)
            result["rain_imd_cv_annual_pct"] = 100 * statistics.pstdev(totals) / mean if mean else None
            result["rain_imd_monsoon_share_pct"] = 100 * sum(v["monsoon"] for v in years.values()) / sum(totals) if sum(totals) else None
            result["rain_imd_rainy_days"] = statistics.fmean(v["rainy_days"] for v in years.values())
            result["rain_imd_max_1day_mm"] = max(v["max_1day"] for v in years.values())
            result["rain_imd_years_used"] = f"{min(years)}-{max(years)}" if len(years) == max(years) - min(years) + 1 else ", ".join(map(str, years))
        for column, (grid, transform) in self.soil.items():
            cell = self._cell(transform, grid.shape, lon, lat)
            if cell and grid[cell] > 0:
                result[column] = grid[cell]
        # The 0-5 cm export has no silt layer; SoilGrids fractions sum to ~100 %, so silt = 100 - clay - sand.
        if result.get("sg_silt_0_5cm_pct") is None and result.get("sg_clay_0_5cm_pct") and result.get("sg_sand_0_5cm_pct"):
            result["sg_silt_0_5cm_pct"] = 100 - result["sg_clay_0_5cm_pct"] - result["sg_sand_0_5cm_pct"]
        for stem, unit in (("sg_clay", "pct"), ("sg_sand", "pct"), ("sg_silt", "pct"), ("sg_coarse_fragments", "pct"),
                           ("sg_bulk_density", "g_cm3"), ("sg_org_carbon_density", "kg_m3")):
            parts = [(result.get(f"{stem}_{label}_{unit}"), weight) for (_, label), weight in zip(SOILGRID_DEPTHS, (5, 10, 15))]
            if all(v is not None for v, _ in parts):
                result[f"{stem}_0_30cm_{unit}"] = sum(v * w for v, w in parts) / 30
        if self.lines is not None:
            x, y = self.to_utm.transform(lon, lat)
            point = Point(x, y)
            nearest = self.tree.query_nearest(point)
            result["lineament_dem_distance_m"] = min(self.lines[i].distance(point) for i in nearest)
            circle = point.buffer(1000)
            inside = sum(self.lines[i].intersection(circle).length for i in self.tree.query(circle))
            result["lineament_dem_density_1km_km_per_km2"] = (inside / 1000) / math.pi
        return result


class NgdrGeology:
    """GSI NGDR state-scale lithology polygons and fault lines (Uttarakhand only)."""

    def __init__(self):
        self.ok = NGDR_LITHOLOGY.exists() and NGDR_FAULTS.exists()
        self.folds = []
        if not self.ok:
            return
        project = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True).transform
        self.to_utm = project

        def load(path):
            features = json.loads(path.read_text(encoding="utf-8"))["features"]
            return [(shapely_transform(shape(f["geometry"]), lambda xy: np.column_stack(project(xy[:, 0], xy[:, 1]))), f["properties"]) for f in features if f.get("geometry")]

        self.units = load(NGDR_LITHOLOGY)
        self.unit_tree = STRtree([g for g, _ in self.units])
        self.faults = load(NGDR_FAULTS)
        self.fault_tree = STRtree([g for g, _ in self.faults])
        thrusts = [(g, p) for g, p in self.faults if "THRUST" in (p.get("fault_type") or "") or "THRUST" in (p.get("fault_name") or "")]
        self.thrusts = thrusts
        self.thrust_tree = STRtree([g for g, _ in thrusts])
        if NGDR_FOLDS.exists():
            self.folds = load(NGDR_FOLDS)
            self.fold_tree = STRtree([g for g, _ in self.folds])

    @staticmethod
    def _clean(value):
        value = (value or "").strip()
        return "" if value.upper() == "BLANK" else value

    def features(self, lon, lat):
        if not self.ok:
            return {}
        point = Point(*self.to_utm(lon, lat))
        result = {}
        hits = [i for i in self.unit_tree.query(point, predicate="intersects")]
        if not hits:  # outside the Uttarakhand map: fault distances would only reach the state edge
            return {}
        geom, props = self.units[hits[0]]
        result.update({
            "gsi_lithology": self._clean(props.get("lithologic")).rstrip("."),
            "gsi_group": self._clean(props.get("group_name")),
            "gsi_formation": self._clean(props.get("formation")),
            "gsi_age": self._clean(props.get("age")),
            "gsi_map_unit": self._clean(props.get("notation_lithology")),
            "gsi_distance_to_contact_m": geom.boundary.distance(point),
        })
        i = self.fault_tree.query_nearest(point)[0]
        geom, props = self.faults[i]
        result["distance_to_gsi_fault_m"] = geom.distance(point)
        result["gsi_nearest_fault_type"] = self._clean(props.get("fault_type"))
        result["gsi_nearest_fault_name"] = self._clean(props.get("fault_name"))
        result["distance_to_gsi_thrust_m"] = self.thrusts[self.thrust_tree.query_nearest(point)[0]][0].distance(point)
        circle = point.buffer(1000)
        inside = sum(self.faults[j][0].intersection(circle).length for j in self.fault_tree.query(circle))
        result["gsi_fault_density_1km_km_per_km2"] = (inside / 1000) / math.pi
        if self.folds:
            i = self.fold_tree.query_nearest(point)[0]
            geom, props = self.folds[i]
            result["distance_to_gsi_fold_axis_m"] = geom.distance(point)
            result["gsi_nearest_fold_type"] = self._clean(props.get("fold_type"))
            result["distance_to_gsi_anticline_m"] = min(
                (g.distance(point) for g, p in self.folds if "ANTI" in (p.get("fold_type") or "")), default=None)
            result["distance_to_gsi_syncline_m"] = min(
                (g.distance(point) for g, p in self.folds if "SYN" in (p.get("fold_type") or "")), default=None)
            circle = point.buffer(2000)
            result["gsi_fold_axes_within_2km"] = len(self.fold_tree.query(circle, predicate="intersects"))
        return result


# --------------------------------------------------------------------------- columns
COLUMNS = [
    # identity and cleaned location
    ("record_id", "", "Common file", "Copied."),
    ("source_id", "", "Common file", "Copied."),
    ("source_dataset", "", "Common file", "Copied."),
    ("spring_name", "", "Common file", "Copied."),
    ("village", "", "Common file", "Copied."),
    ("district_clean", "", "Common file", "District with spelling variants unified (Nanital to Nainital, Tehri-Garhwal to Tehri Garhwal, Pauri to Pauri Garhwal)."),
    ("latitude_dd", "decimal degrees", "Common file", "Source latitude parsed as a number."),
    ("longitude_dd", "decimal degrees", "Common file", "Source longitude parsed as a number."),
    ("coordinate_status", "", "Derived", "ok, missing, or outside_study_region (lat 28.5-33.5, lon 75.5-81.5). Layer values are only computed for ok."),
    ("coordinate_precision_decimals", "", "Derived", "Decimal places in the source latitude; 2 or fewer means about 1 km uncertainty."),
    ("coordinate_correction", "", "Derived", "Blank, or what was corrected in the source coordinate and why (only where the fix is certain)."),
    ("colocated_group_id", "", "Derived", "Records from different rows within 30 m of each other share a group id; likely the same spring listed twice. Not merged."),
    ("colocated_group_size", "", "Derived", "Number of records in the group."),
    # cleaned source values
    ("source_elevation_m", "m", "Common file", "Source elevation parsed as a number."),
    ("source_discharge_lpm_low", "L/min", "Common file", "Lowest number in the source discharge text."),
    ("source_discharge_lpm_high", "L/min", "Common file", "Highest number in the source discharge text."),
    ("source_discharge_parse_note", "", "Derived", "How the low/high values were read from the text."),
    ("source_max_flow_lpm_converted", "L/min", "Common file (Rathi 2021)", "Max flow in m3/day x 1000 / 1440. Unit conversion only."),
    ("source_recharge_area_ha_low", "ha", "Common file", "Lowest number in the source recharge-area text (WATSAN text estimates, Atlas field delineation)."),
    ("source_recharge_area_ha_high", "ha", "Common file", "Highest number in the source recharge-area text; equals low for single values."),
    ("source_springshed_area_ha_converted", "ha", "Common file (Rathi 2021)", "Springshed area in km2 x 100."),
    ("source_catchment_area_ha", "ha", "Common file (Chamba report)", "Surface micro-watershed area; not a recharge area."),
    ("source_rainfall_mm", "mm/year", "Common file", "Source rainfall parsed as a number."),
    ("source_slope_deg", "degrees", "Common file", "Source slope parsed as a number (WATSAN, Himmotthan, Chamba)."),
    ("source_tds_mg_l", "mg/l", "Common file", "Source TDS parsed as a number."),
    ("source_ph", "", "Common file", "Source pH parsed as a number."),
    # DEM
    ("dem_elevation_m", "m (EGM2008)", "Copernicus DEM GLO-30", "Elevation of the 30 m cell containing the coordinate."),
    ("dem_minus_source_elevation_m", "m", "Derived", "DEM elevation minus source elevation; large gaps point to coordinate or elevation errors."),
    ("elevation_match_distance_m", "m", "Derived from Copernicus DEM GLO-30", f"Only where the gap is over {ELEVATION_GAP_M} m: distance to the nearest DEM cell within {ELEVATION_MATCH_TOLERANCE_M} m of the source elevation, searched up to {ELEVATION_SEARCH_M / 1000:.0f} km. Small = the coordinate is a little off on a steep slope; blank = no such cell nearby, so the coordinate or the source elevation is badly wrong."),
    ("dem_slope_deg", "degrees", "Copernicus DEM GLO-30", "Slope at the cell (central differences)."),
    ("dem_aspect_deg", "degrees from north", "Copernicus DEM GLO-30", "Direction the slope faces; blank when slope < 2 degrees."),
    ("dem_aspect_class", "", "Copernicus DEM GLO-30", "8-point aspect class, or Flat."),
    ("dem_mean_slope_500m_deg", "degrees", "Copernicus DEM GLO-30", "Mean slope within 500 m of the coordinate."),
    ("dem_relief_1km_m", "m", "Copernicus DEM GLO-30", "Highest minus lowest elevation within 1 km."),
    ("dem_upslope_relief_1km_m", "m", "Copernicus DEM GLO-30", "Highest elevation within 1 km minus the spring cell elevation (head available upslope)."),
    ("dem_tpi_300m_m", "m", "Copernicus DEM GLO-30", "Spring elevation minus mean elevation within 300 m; negative = valley/hollow position."),
    ("dem_drainage_area_ha", "ha", "Derived from Copernicus DEM GLO-30", "Upslope area draining to the spring cell: depression-filled DEM, multiple-flow-direction routing (Freeman 1991). The surface catchment above the spring, not its recharge area (scripts/spring_hydrology.py)."),
    ("dem_drainage_area_max30m_ha", "ha", "Derived from Copernicus DEM GLO-30", "Largest drainage area in the 3 x 3 cells around the spring (allows for ~30 m GPS error). A big jump from the cell value means a hollow or stream line lies next to the point."),
    ("dem_drainage_area_d8_ha", "ha", "Derived from Copernicus DEM GLO-30", "Same as dem_drainage_area_ha but with single-direction (D8) routing. Kept as a check; D8 is noisier at a single cell."),
    ("dem_twi", "", "Derived from Copernicus DEM GLO-30", "Topographic wetness index ln(a / tan slope), a = MFD drainage area per metre of contour. Higher = wetter, more convergent position. Typical hillslope 4-8, hollows and valley floors 8-14."),
    ("dem_distance_to_stream_m", "m", "Derived from Copernicus DEM GLO-30", f"Straight-line distance to the nearest DEM-derived stream cell (D8 drainage area at least {STREAM_THRESHOLD_KM2} km2)."),
    ("dem_nearest_stream_order", "", "Derived from Copernicus DEM GLO-30", "Strahler order of that nearest stream cell (1 = headwater)."),
    ("dem_nearest_stream_area_km2", "km2", "Derived from Copernicus DEM GLO-30", "D8 drainage area of that nearest stream cell."),
    ("dem_height_above_stream_m", "m", "Derived from Copernicus DEM GLO-30", "Height above the stream the spring cell drains to, along its D8 flow path (HAND)."),
    ("dem_catchment_window_edge", "", "Derived from Copernicus DEM GLO-30", "Y when the spring cell's catchment reaches the edge of the +/- 20 km DEM window, so the drainage areas are minimums (spring on a large river)."),
    ("cartodem_elevation_m", "m (as supplied by NRSC)", "NRSC CartoDEM v3 30 m (Bhoonidhi)", "Elevation of the CartoDEM cell containing the coordinate."),
    ("cartodem_minus_copernicus_m", "m", "Derived", "CartoDEM minus Copernicus elevation. A check on both DEMs; the datums differ slightly."),
    ("cartodem_slope_deg", "degrees", "NRSC CartoDEM v3 30 m (Bhoonidhi)", "Slope at the cell from its 3 x 3 neighbourhood."),
    # Land cover
    ("wc_point_class_code", "", "ESA WorldCover 2021 v200", "Class code of the 10 m cell at the coordinate."),
    ("wc_point_class", "", "ESA WorldCover 2021 v200", "Class name at the coordinate."),
    ("wc_majority_500m_class", "", "ESA WorldCover 2021 v200", "Most common class within 500 m."),
] + [
    (f"wc_share_500m_{name}_pct", "%", "ESA WorldCover 2021 v200", f"Share of {WORLDCOVER_CLASSES[code].lower()} within 500 m.")
    for code, name in WC_SHARE_COLUMNS.items()
] + [
    # Climate
    ("rain_chirps_mean_annual_mm_2018_2025", "mm/year", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A", "Mean of annual totals 2018-2025 at the ~5 km cell."),
    ("rain_chirps_min_annual_mm_2018_2025", "mm/year", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A", "Driest year 2018-2025."),
    ("rain_chirps_max_annual_mm_2018_2025", "mm/year", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A", "Wettest year 2018-2025."),
    ("rain_chirps_cv_annual_pct", "%", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A", "Year-to-year coefficient of variation."),
    ("rain_chirps_monsoon_share_pct", "%", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-M", "Share of rain falling June-September (mean 2018-2025)."),
    ("rain_chirps_dry_season_mm", "mm", "CHIRPS v2 via FAO WaPOR v3 L1-PCP-M", "Mean November-April total (2018-2025 seasons within calendar years)."),
    ("et0_wapor_mean_annual_mm_2018_2025", "mm/year", "FAO WaPOR v3 L1-RET-A", "Mean annual reference evapotranspiration at the ~30 km cell."),
    ("aridity_index_p_over_et0", "", "Derived", "Mean annual CHIRPS rain divided by mean annual ET0."),
    ("rain_source_minus_chirps_mm", "mm/year", "Derived", "Source rainfall minus CHIRPS mean, where the source gives rainfall."),
    ("rain_imd_mean_annual_mm", "mm/year", "IMD 0.25 degree gridded daily rainfall", "Mean of the yearly totals 2021-2025 at the ~25 km cell."),
    ("rain_imd_min_annual_mm", "mm/year", "IMD 0.25 degree gridded daily rainfall", "Driest year 2021-2025."),
    ("rain_imd_max_annual_mm", "mm/year", "IMD 0.25 degree gridded daily rainfall", "Wettest year 2021-2025."),
    ("rain_imd_cv_annual_pct", "%", "IMD 0.25 degree gridded daily rainfall", "Year-to-year coefficient of variation, 2021-2025."),
    ("rain_imd_monsoon_share_pct", "%", "IMD 0.25 degree gridded daily rainfall", "Share of 2021-2025 rain falling 1 June-30 September."),
    ("rain_imd_rainy_days", "days/year", "IMD 0.25 degree gridded daily rainfall", "Mean days per year with at least 2.5 mm (IMD rainy-day definition)."),
    ("rain_imd_max_1day_mm", "mm", "IMD 0.25 degree gridded daily rainfall", "Wettest single day, 2021-2025."),
    ("rain_imd_years_used", "", "IMD 0.25 degree gridded daily rainfall", "IMD years found and used."),
] + [
    (f"rain_imd_{year}_mm", "mm", "IMD 0.25 degree gridded daily rainfall", f"Total rain in {year}.") for year in range(2021, 2026)
] + [
    # Soil
    ("soil_hwsd2_smu_id", "", "HWSD v2.0", "Soil mapping unit at the ~1 km cell."),
    ("soil_dominant_wrb", "", "HWSD v2.0", "WRB soil name of the dominant soil in the mapping unit."),
    ("soil_dominant_share_pct", "%", "HWSD v2.0", "Share of the mapping unit covered by the dominant soil."),
    ("soil_drainage", "", "HWSD v2.0", "Drainage class of the dominant soil."),
    ("soil_awc_mm_per_m", "mm/m", "HWSD v2.0", "Available water capacity of the dominant soil."),
    ("soil_topsoil_sand_pct", "%", "HWSD v2.0", "Sand, 0-20 cm, dominant soil."),
    ("soil_topsoil_silt_pct", "%", "HWSD v2.0", "Silt, 0-20 cm, dominant soil."),
    ("soil_topsoil_clay_pct", "%", "HWSD v2.0", "Clay, 0-20 cm, dominant soil."),
    ("soil_topsoil_texture_usda", "", "HWSD v2.0", "USDA texture class, 0-20 cm."),
    ("soil_topsoil_coarse_fragments_pct", "%", "HWSD v2.0", "Coarse fragments, 0-20 cm."),
    ("soil_topsoil_org_carbon_pct", "%", "HWSD v2.0", "Organic carbon, 0-20 cm."),
] + [
    (f"{stem}_{label}_{unit.replace('%', 'pct').replace('/', '_')}", unit, "ISRIC SoilGrids 2.0 (250 m)",
     f"{text}, {depth.replace('cm', ' cm')}, predicted mean." + (" Derived as 100 - clay - sand (no silt export at this depth)." if (prop, label) == ("silt", "0_5cm") else ""))
    for prop, stem, unit, _, text in SOILGRID_PROPERTIES for depth, label in SOILGRID_DEPTHS
] + [
    (f"{stem}_0_30cm_{unit.replace('%', 'pct').replace('/', '_')}", unit, "Derived from ISRIC SoilGrids 2.0",
     f"{text.split(' (')[0]}, 0-30 cm, depth-weighted mean of the three layers.")
    for _, stem, unit, _, text in SOILGRID_PROPERTIES
] + [
    # Geology placeholders
    ("gsi_lithology", "", "GSI NGDR Uttarakhand lithology (Bhukosh)", "Lithology description of the map polygon containing the spring. Uttarakhand only; GSI columns are blank for springs outside it."),
    ("gsi_group", "", "GSI NGDR Uttarakhand lithology", "Stratigraphic group (e.g. Garhwal, Jaunsar, Central Crystalline)."),
    ("gsi_formation", "", "GSI NGDR Uttarakhand lithology", "Formation name."),
    ("gsi_age", "", "GSI NGDR Uttarakhand lithology", "Geological age."),
    ("gsi_map_unit", "", "GSI NGDR Uttarakhand lithology", "Map unit notation."),
    ("gsi_distance_to_contact_m", "m", "GSI NGDR Uttarakhand lithology", "Distance to the edge of the spring's map polygon (a rock-type contact or map edge)."),
    ("distance_to_gsi_fault_m", "m", "GSI NGDR Uttarakhand faults (Bhukosh)", "Distance to the nearest mapped fault or thrust (observed, inferred or interpreted)."),
    ("gsi_nearest_fault_type", "", "GSI NGDR Uttarakhand faults", "Type of that nearest fault (FAULT, FAULT INFERRED, THRUST, ...)."),
    ("gsi_nearest_fault_name", "", "GSI NGDR Uttarakhand faults", "Name of that fault where GSI gives one (e.g. MAIN BOUNDART THRUST (MBT), as spelt by GSI)."),
    ("distance_to_gsi_thrust_m", "m", "GSI NGDR Uttarakhand faults", "Distance to the nearest mapped thrust."),
    ("gsi_fault_density_1km_km_per_km2", "km/km2", "GSI NGDR Uttarakhand faults", "Length of mapped faults within 1 km, per km2."),
    ("distance_to_gsi_fold_axis_m", "m", "GSI NGDR Uttarakhand folds (Bhukosh)", "Distance to the nearest mapped fold axis (290 axes in the state layer)."),
    ("gsi_nearest_fold_type", "", "GSI NGDR Uttarakhand folds", "Type of that fold (ANTICLINE, SYNCLINE, ANTIFORM, SYNFORM, OVERTURNED ...)."),
    ("distance_to_gsi_anticline_m", "m", "GSI NGDR Uttarakhand folds", "Distance to the nearest anticline or antiform axis (rocks dip away; fractured crest)."),
    ("distance_to_gsi_syncline_m", "m", "GSI NGDR Uttarakhand folds", "Distance to the nearest syncline or synform axis (rocks dip inward; can trap groundwater)."),
    ("gsi_fold_axes_within_2km", "count", "GSI NGDR Uttarakhand folds", "Number of fold axes within 2 km."),
    ("lineament_dem_distance_m", "m", "Derived from Copernicus DEM GLO-30", "Distance to the nearest DEM lineament candidate (scripts/extract_dem_lineaments.py). Unvalidated."),
    ("lineament_dem_density_1km_km_per_km2", "km/km2", "Derived from Copernicus DEM GLO-30", "Length of DEM lineament candidates within 1 km, per km2."),
    ("processing_notes", "", "Derived", "Row-level notes on missing or questionable inputs."),
]
COLUMN_NAMES = [name for name, *_ in COLUMNS]


def colocated_groups(rows):
    """Group records (from any rows) whose coordinates are within 30 m."""
    cell = 0.0005
    buckets = {}
    for index, row in enumerate(rows):
        if row["coordinate_status"] == "ok":
            key = (int(row["latitude_dd"] / cell), int(row["longitude_dd"] / cell))
            buckets.setdefault(key, []).append(index)
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for (ky, kx), members in buckets.items():
        neighbours = [j for dy in (-1, 0, 1) for dx in (-1, 0, 1) for j in buckets.get((ky + dy, kx + dx), [])]
        for i in members:
            for j in neighbours:
                if j <= i:
                    continue
                a, b = rows[i], rows[j]
                m_lat, m_lon = metres_per_degree(a["latitude_dd"])
                d = math.hypot((a["latitude_dd"] - b["latitude_dd"]) * m_lat, (a["longitude_dd"] - b["longitude_dd"]) * m_lon)
                if d <= 30:
                    parent[find(i)] = find(j)
    groups = {}
    for i in range(len(rows)):
        if rows[i]["coordinate_status"] == "ok":
            groups.setdefault(find(i), []).append(i)
    counter = 0
    for members in sorted(groups.values(), key=lambda m: m[0]):
        if len(members) > 1:
            counter += 1
            for i in members:
                rows[i]["colocated_group_id"] = f"COLOC-{counter:04d}"
                rows[i]["colocated_group_size"] = len(members)


def clean_row(src):
    notes = []
    row = {name: "" for name in COLUMN_NAMES}
    for name in ("record_id", "source_id", "source_dataset", "spring_name", "village"):
        row[name] = src[name]
    district = src["district"].strip()
    row["district_clean"] = DISTRICT_FIXES.get(district.lower(), district)
    lat, lon = to_float(src["latitude_source_value"]), to_float(src["longitude_source_value"])
    if src["record_id"] in COORDINATE_FIXES:
        fix_lat, fix_lon, why = COORDINATE_FIXES[src["record_id"]]
        lat, lon = fix_lat or lat, fix_lon or lon
        row["coordinate_correction"] = why
    if src["record_id"] in COORDINATE_NOTES:
        notes.append(COORDINATE_NOTES[src["record_id"]])
    if lat is None or lon is None:
        row["coordinate_status"] = "missing"
        notes.append("no coordinates in source; layer values not computed")
    else:
        row["latitude_dd"], row["longitude_dd"] = lat, lon
        decimals = len(src["latitude_source_value"].split(".")[1]) if "." in src["latitude_source_value"] else 0
        row["coordinate_precision_decimals"] = decimals
        inside = REGION["lat_min"] <= lat <= REGION["lat_max"] and REGION["lon_min"] <= lon <= REGION["lon_max"]
        row["coordinate_status"] = "ok" if inside else "outside_study_region"
        if not inside:
            notes.append("coordinate outside study region; likely a typing error in the source")
        if decimals <= 2 and not row["coordinate_correction"]:
            notes.append("coordinate rounded to about 1 km; point layer values are indicative only")

    row["source_elevation_m"] = to_float(src["elevation_m_source_value"])
    low, high, note = parse_numbers(src["discharge_lpm_source_value"])
    row["source_discharge_lpm_low"], row["source_discharge_lpm_high"], row["source_discharge_parse_note"] = low, high, note
    max_flow = to_float(src.get("discharge_max_m3_per_day_source_value", ""))
    row["source_max_flow_lpm_converted"] = None if max_flow is None else max_flow * 1000 / 1440
    low, high, _ = parse_numbers(src["recharge_area_ha_source_value"])
    row["source_recharge_area_ha_low"], row["source_recharge_area_ha_high"] = low, high
    shed = to_float(src.get("springshed_area_km2_source_value", ""))
    row["source_springshed_area_ha_converted"] = None if shed is None else shed * 100
    row["source_catchment_area_ha"] = to_float(src.get("catchment_area_ha_source_value", ""))
    low, high, _ = parse_numbers(src["rainfall_source_value"])
    row["source_rainfall_mm"] = low if low == high else None
    row["source_slope_deg"] = to_float(src["slope_degrees_source_value"])
    row["source_tds_mg_l"] = to_float(src["tds_source_value"])
    row["source_ph"] = to_float(src["ph_source_value"])
    row["_notes"] = notes
    return row


def open_layers(points, cache, local_layers, lineaments=LINEAMENTS_FILE):
    """Open every layer once; DEM and WorldCover tiles covering the points are downloaded into the cache."""
    cache = Path(cache)
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    if Path("/root/.ccr/ca-bundle.crt").exists():
        os.environ.setdefault("CURL_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
    print("Opening layers")
    layers = argparse.Namespace(
        dem=[rasterio.open(p) for p in dem_tiles_for(points, cache)],
        wc=[rasterio.open(p) for p in worldcover_tiles_for(points, cache)],
        pcp_a=WaporStack("L1-PCP-A", [str(y) for y in YEARS]),
        pcp_m=WaporStack("L1-PCP-M", [f"{y}-{m:02d}" for y in YEARS for m in range(1, 13)]),
        ret_a=WaporStack("L1-RET-A", [str(y) for y in YEARS]),
        hwsd=Hwsd(cache),
        local=LocalLayers(local_layers, lineaments),
        ngdr=NgdrGeology(),
    )
    ngdr = layers.ngdr
    print("GSI NGDR geology: " + (f"{len(ngdr.units)} lithology polygons, {len(ngdr.faults)} faults, {len(ngdr.folds)} fold axes" if ngdr.ok else "not found"))
    print("Local layers: " + ("; ".join(layers.local.found) or "none found"))
    return layers


def point_features(layers, lon, lat, source_elevation=None, notes=None):
    """All layer values at one coordinate, keyed by the spring_features_v1 column names."""
    notes = [] if notes is None else notes
    row = dem_features(layers.dem, lon, lat)
    if row.get("dem_elevation_m") is not None and source_elevation is not None:
        row["dem_minus_source_elevation_m"] = row["dem_elevation_m"] - source_elevation
        if abs(row["dem_minus_source_elevation_m"]) > ELEVATION_GAP_M:
            notes.append(f"DEM and source elevation differ by more than {ELEVATION_GAP_M} m; check coordinate")
            row["elevation_match_distance_m"] = elevation_match_distance(layers.dem, lon, lat, source_elevation)
    row.update(hydrology_features(read_window, centre_index, metres_per_degree, layers.dem, lon, lat))
    row.update(worldcover_features(layers.wc, lon, lat))

    annual = [layers.pcp_a.sample(str(y), lon, lat) for y in YEARS]
    annual = [v for v in annual if not math.isnan(v)]
    if annual:
        mean = statistics.fmean(annual)
        row["rain_chirps_mean_annual_mm_2018_2025"] = mean
        row["rain_chirps_min_annual_mm_2018_2025"] = min(annual)
        row["rain_chirps_max_annual_mm_2018_2025"] = max(annual)
        row["rain_chirps_cv_annual_pct"] = 100 * statistics.pstdev(annual) / mean if mean else None
        monthly = {(y, m): layers.pcp_m.sample(f"{y}-{m:02d}", lon, lat) for y in YEARS for m in range(1, 13)}
        year_totals = [sum(monthly[(y, m)] for m in range(1, 13)) for y in YEARS]
        monsoon = [sum(monthly[(y, m)] for m in (6, 7, 8, 9)) for y in YEARS]
        dry = [sum(monthly[(y, m)] for m in (1, 2, 3, 4, 11, 12)) for y in YEARS]
        if not any(math.isnan(v) for v in year_totals) and sum(year_totals):
            row["rain_chirps_monsoon_share_pct"] = 100 * sum(monsoon) / sum(year_totals)
            row["rain_chirps_dry_season_mm"] = statistics.fmean(dry)
        et0 = [layers.ret_a.sample(str(y), lon, lat) for y in YEARS]
        et0 = [v for v in et0 if not math.isnan(v)]
        if et0:
            row["et0_wapor_mean_annual_mm_2018_2025"] = statistics.fmean(et0)
            row["aridity_index_p_over_et0"] = mean / statistics.fmean(et0)
    row.update(layers.hwsd.features(lon, lat))
    row.update(layers.local.features(lon, lat))
    row.update(layers.ngdr.features(lon, lat))  # blank outside Uttarakhand
    if row.get("cartodem_elevation_m") is not None and row.get("dem_elevation_m") is not None:
        row["cartodem_minus_copernicus_m"] = row["cartodem_elevation_m"] - row["dem_elevation_m"]
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", default=os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
    parser.add_argument("--local-layers", default=os.environ.get("SPRING_LOCAL_LAYERS", str(ROOT / ".local_layers")))
    parser.add_argument("--lineaments", default=str(LINEAMENTS_FILE))
    args = parser.parse_args()
    cache = Path(args.cache)

    with COMMON_CSV.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = [clean_row(src) for src in source_rows]
    colocated_groups(rows)
    points = [(r["latitude_dd"], r["longitude_dd"]) for r in rows if r["coordinate_status"] == "ok"]

    layers = open_layers(points, cache, args.local_layers, args.lineaments)
    for index, row in enumerate(rows):
        if row["coordinate_status"] != "ok":
            continue
        row.update(point_features(layers, row["longitude_dd"], row["latitude_dd"], row["source_elevation_m"], row["_notes"]))
        if row["source_rainfall_mm"] is not None and row.get("rain_chirps_mean_annual_mm_2018_2025", "") != "":
            row["rain_source_minus_chirps_mm"] = row["source_rainfall_mm"] - row["rain_chirps_mean_annual_mm_2018_2025"]
        if (index + 1) % 200 == 0:
            print(f"  {index + 1} rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "spring_features_v1.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMN_NAMES)
        for row in rows:
            row["processing_notes"] = "; ".join(row.pop("_notes"))
            out = []
            for name in COLUMN_NAMES:
                value = row.get(name, "")
                if isinstance(value, (float, np.floating)):
                    digits = (6 if name in ("latitude_dd", "longitude_dd") else 3 if name == "aridity_index_p_over_et0"
                              else 2 if name == "dem_twi" or "drainage_area" in name or "bulk_density" in name else 1)
                    value = fmt(value, digits)
                elif value is None:
                    value = ""
                out.append(value)
            writer.writerow(out)

    with (OUT_DIR / "spring_features_v1_data_dictionary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["column", "unit", "source", "method"])
        writer.writerows(COLUMNS)

    coverage = []
    prefixes = sorted({r["record_id"][:3] for r in rows})
    for name in COLUMN_NAMES:
        counts = {p: sum(1 for r in rows if r["record_id"][:3] == p and r.get(name, "") not in ("", None)) for p in prefixes}
        totals = {p: sum(1 for r in rows if r["record_id"][:3] == p) for p in prefixes}
        coverage.append([name] + [f"{100 * counts[p] / totals[p]:.0f}" for p in prefixes] + [f"{100 * sum(counts.values()) / len(rows):.0f}"])
    with (OUT_DIR / "spring_features_v1_coverage_pct.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["column"] + [f"{p}_pct_filled" for p in prefixes] + ["all_pct_filled"])
        writer.writerows(coverage)

    metadata = {
        "built": date.today().isoformat(),
        "input": str(COMMON_CSV.relative_to(ROOT)),
        "records": len(rows),
        "records_with_layer_values": len(points),
        "coordinate_status_counts": {s: sum(1 for r in rows if r["coordinate_status"] == s) for s in ("ok", "missing", "outside_study_region")},
        "colocated_groups": len({r["colocated_group_id"] for r in rows if r["colocated_group_id"]}),
        "layers": {
            "Copernicus DEM GLO-30": {"url_pattern": DEM_URL, "resolution": "1 arc-second (~30 m)", "vertical_datum": "EGM2008",
                                      "licence": "Copernicus DEM licence (free use with attribution: produced using Copernicus WorldDEM-30, DLR/Airbus, ESA)"},
            "ESA WorldCover 2021 v200": {"url_pattern": WC_URL, "resolution": "10 m", "licence": "CC BY 4.0, ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021)"},
            "CHIRPS v2 via FAO WaPOR v3 L1-PCP-A / L1-PCP-M": {"url_pattern": WAPOR_URL, "years": YEARS, "resolution": "0.05 degree (~5 km)",
                                                              "licence": "FAO WaPOR CC BY-NC-SA 4.0 (non-commercial); CHIRPS by UCSB Climate Hazards Center"},
            "FAO WaPOR v3 L1-RET-A": {"url_pattern": WAPOR_URL, "years": YEARS, "resolution": "~30 km", "licence": "CC BY-NC-SA 4.0"},
            "HWSD v2.0": {"urls": HWSD_URLS, "resolution": "30 arc-second (~1 km)", "licence": "FAO/IIASA, CC BY-NC-SA 3.0 IGO (non-commercial)"},
            "NRSC CartoDEM v3 30 m": {"source": "Bhoonidhi (bhoonidhi.nrsc.gov.in), downloaded by hand 2026-10-10; 1-degree tiles P5_PAN_CD_N*_E*_30m",
                                      "licence": "NRSC data policy; raw tiles not committed"},
            "IMD 0.25 degree daily gridded rainfall": {"source": "IMD Pune, files RF25_ind2021_rfp25.nc to RF25_ind2025_rfp25.nc (calendar years 2021-2025), downloaded by hand 2026-10-10 (2025) and 2026-10-12 (2021-2024)",
                                                       "licence": "IMD data policy; raw file not committed"},
            "ISRIC SoilGrids 2.0": {"source": "soilgrids.org map export, mean, bbox lon 76-81 lat 28.7-32.4; 0-5 cm downloaded by hand 2026-10-10, "
                                              "5-15 and 15-30 cm (files named by property) on 2026-10-12",
                                    "licence": "CC BY 4.0",
                                    "file_identification": "The 0-5 cm exports were saved unnamed as out.tif ... out (4).tif. Each was matched to the named "
                                                           "5-15 cm file it correlates with pixel by pixel (Spearman 0.95-0.99): out=bdod, out (1)=clay, "
                                                           "out (2)=cfvo (coarse fragments), out (3)=sand, out (4)=organic carbon. There is no 0-5 cm silt file. "
                                                           "The first build (2026-10-10) had identified these by value range and wrongly read out (2) as organic "
                                                           "carbon, out (3) as silt and out (4) as sand; fixed 2026-10-12. Organic carbon is treated as organic "
                                                           "carbon density (ocd, hg/m3) as Rajat described the download; if it was soil organic carbon "
                                                           "content (soc, dg/kg) the column is g/kg instead of kg/m3."},
            "GSI NGDR Uttarakhand lithology, faults and folds": {"files": [str(p.relative_to(ROOT)) for p in (NGDR_LITHOLOGY, NGDR_FAULTS, NGDR_FOLDS)],
                                                         "source": "GSI Bhukosh / NGDR state layers (SRC-013, SRC-014, SRC-015), added to the repo 2026-10-10 and 2026-10-12",
                                                         "note": "State-scale map; a spring's polygon is a map overlay, not a field observation."},
            "DEM lineament candidates": {"file": str(LINEAMENTS_FILE.relative_to(ROOT)), "method": "scripts/extract_dem_lineaments.py"},
            "DEM hydrology": {"method": "scripts/spring_hydrology.py: depression filling and D8 routing with pyflwdir, Freeman (1991) MFD area, "
                                        "TWI = ln(a / tan slope)", "stream_threshold_km2": STREAM_THRESHOLD_KM2,
                              "window": "+/- 5 km around each spring, +/- 20 km when the D8 catchment reaches the edge"},
        },
        "local_layers_found": layers.local.found,
        "not_acquired": {
            "Bhuvan LULC 1:50k": "Bhuvan services blocked from the build environment; download needs a request.",
        },
    }
    (OUT_DIR / "spring_features_v1_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({k: metadata[k] for k in ("records", "records_with_layer_values", "coordinate_status_counts", "colocated_groups")}, indent=2))


if __name__ == "__main__":
    main()

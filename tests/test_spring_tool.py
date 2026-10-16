"""Modules B and C and the tool server. Tests that need the elevation map skip when its tile is not in the layer cache."""

import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import module_b_springshed as module_b  # noqa: E402
import module_c_di_impact as module_c  # noqa: E402
import spring_tool_server as server  # noqa: E402

NAULI = {"name": "Nauli Dhara", "latitude": 29.91903, "longitude": 78.55647, "elevation_m": 1481}
CACHE = Path(os.environ.get("SPRING_LAYER_CACHE", str(ROOT / ".layer_cache")))
HAS_DEM = (CACHE / "dem" / "Copernicus_DSM_COG_10_N29_00_E078_00_DEM.tif").is_file()


def test_rathi_fit_uses_all_35_springsheds():
    fit = module_b.rathi_fit()
    assert fit["n"] == 35
    assert 0.5 < fit["b"] < 0.9  # area grows more slowly than flow


def test_target_area_from_flow_readings():
    default = module_b.target_area({})
    assert (default["low"], default["mid"], default["high"]) == module_b.DEFAULT_AREA_HA
    small, big = module_b.target_area({"monsoon_flow_lpm": 10}), module_b.target_area({"monsoon_flow_lpm": 60})
    assert small["low"] < small["mid"] < small["high"] and small["mid"] < big["mid"]
    lean = module_b.target_area({"lean_flow_lpm": 3})
    assert lean["kind"] == "lean flow" and lean["high"] / lean["mid"] > small["high"] / small["mid"]  # wider when guessed


def test_factor_weights_sum_to_100():
    factors = module_b.load_factors()
    assert set(factors) == {"slope", "land_cover", "rock", "structure", "soil"}
    assert sum(f["weight"] for f in factors.values()) == 100
    assert all(0 <= s <= 1 for f in factors.values() for s in f["classes"].values())


def test_soil_classes():
    assert module_b.soil_class(5, 80).startswith("Sandy (")
    assert module_b.soil_class(15, 60).startswith("Sandy loam")
    assert module_b.soil_class(24, 35).startswith("Loam")
    assert module_b.soil_class(30, 30).startswith("Clay loam")
    assert module_b.soil_class(45, 20).startswith("Clay (")
    classes = module_b.load_factors()["soil"]["classes"]
    assert all(module_b.soil_class(c, s) in classes for c, s in ((5, 80), (15, 60), (24, 35), (30, 30), (45, 20)))


def test_soilgrids_folder_layouts(tmp_path):
    import build_spring_features as layers_mod
    (tmp_path / "0-5 soilgrids").mkdir()
    (tmp_path / "0-5 soilgrids" / "Slit.tif").write_bytes(b"")
    (tmp_path / "clay_5-15cm_mean.tif").write_bytes(b"")
    assert layers_mod.soilgrids_file(tmp_path, "silt_0-5cm_mean").name == "Slit.tif"
    assert layers_mod.soilgrids_file(tmp_path, "clay_5-15cm_mean").name == "clay_5-15cm_mean.tif"
    assert layers_mod.soilgrids_file(tmp_path, "sand_0-5cm_mean") is None


def test_terrain_tile_encoding_round_trips():
    import struct
    import zlib
    heights = np.array([[0.0, 1481.25], [-20.5, 4000.0]], np.float32)
    png = server.Terrain._png(heights)
    data, i = b"", 8
    while i < len(png):
        n = struct.unpack(">I", png[i:i + 4])[0]
        if png[i + 4:i + 8] == b"IDAT":
            data += png[i + 8:i + 8 + n]
        i += 12 + n
    rgb = np.frombuffer(zlib.decompress(data), np.uint8).reshape(2, 7)[:, 1:].reshape(2, 2, 3).astype(float)
    decoded = rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768
    assert np.allclose(decoded, heights, atol=0.01)


def test_detached_area_found_along_a_fault():
    """A spring on a slope facing west; a fault runs from the spring east, over the ridge, into higher forest."""
    from affine import Affine
    from shapely.geometry import LineString, box
    from shapely import points
    n, cell = 80, 30.0
    t = Affine(cell, 0, 0, 0, -cell, n * cell)
    rows, cols = np.indices((n, n))
    xs, ys = t.c + (cols + 0.5) * cell, t.f - (rows + 0.5) * cell
    row = col = 40
    sx, sy = xs[row, col], ys[row, col]
    # ground rises east of the spring to a ridge at col 50, dips to a saddle, then rises again beyond it
    z = 1000 + np.where(cols <= 50, (cols - 40) * 6.0, 60 - (cols - 50) * 1.0 + np.clip(cols - 56, 0, None) * 5.0)
    z = z.astype(float)
    dist = np.hypot(xs - sx, ys - sy)
    core = (cols >= 38) & (cols <= 50) & (np.abs(rows - row) <= 8)  # the spring's own catchment
    fault = LineString([(sx, sy), (sx + 2400, sy)])
    ctx = {"z": z, "t": t, "dist": dist, "bearing": np.zeros_like(z), "valid": np.ones_like(core), "water": np.zeros_like(core),
           "attached": core, "potential": np.full(z.shape, 0.8), "row": row, "col": col, "z_s": 1000.0,
           "conduits": [(fault, "GSI fault", "Test thrust (thrust)")], "cell_points": points(xs.ravel(), ys.ravel()),
           "spring_utm": (sx, sy), "up_dip": None, "unit_names": np.full(z.shape, "", dtype=object), "target_mid": 2.0,
           "cell_ha": cell * cell / 1e4, "land": np.full(z.shape, 10), "soil": None, "smooth": 10.0,
           "to_lonlat": lambda x, y: (x, y), "window_utm": box(0, 0, n * cell, n * cell)}
    found, masks, n_links = module_b._detached(ctx)
    assert n_links == 1 and found
    d = found[0]
    assert d["link"]["kind"] == "GSI fault" and d["height_above_spring_m"]["min"] >= module_b.DETACHED_MIN_HEAD_M
    assert not (masks[0] & core).any()
    assert 1.5 <= d["area_ha"] <= 2.5
    # with no fault near the spring, nothing is found
    ctx["conduits"] = [(LineString([(sx, sy + 900), (sx + 2400, sy + 900)]), "GSI fault", "Far fault")]
    assert module_b._detached(ctx)[0] == []


def test_di_site_in_a_detached_area():
    far = Point(78.57, 29.93).buffer(0.002)
    b = {"result": {"geology": None}, "_zones": {"small": None, "likely": None, "large": None, "catchment": None, "dem": None,
                                                  "spring_elevation_m": None, "detached": [far]}}
    sites = [{"id": "d", "latitude": 29.93, "longitude": 78.57, "roof_area_m2": 100, "first_flush": True, "filter": True}]
    out = module_c.estimate({"spring": NAULI, "field": {}, "di": {"sites": sites, "assumptions": {"annual_rain_mm": 1600}}}, b_output=b)
    assert out["result"]["sites"][0]["location_class"] == "inside_detached"
    assert out["result"]["sites"][0]["share_reaching_spring"] == {"low": 0.05, "mid": 0.2, "high": 0.5}


def test_png_writer_round_trips():
    import base64
    import io
    Image = pytest.importorskip("PIL.Image")
    rgba = np.zeros((4, 6, 4), np.uint8)
    rgba[1, 2] = (10, 20, 30, 40)
    image = Image.open(io.BytesIO(base64.b64decode(module_b._png(rgba).split(",", 1)[1])))
    assert image.size == (6, 4) and (np.array(image) == rgba).all()


def test_di_arithmetic_without_a_zone():
    out = module_c.estimate({"spring": NAULI, "field": {"lean_flow_lpm": 2},
                             "di": {"sites": [{"id": "a", "latitude": 29.92, "longitude": 78.556, "roof_area_m2": 100,
                                               "first_flush": False, "filter": True}],
                                    "assumptions": {"annual_rain_mm": 1600}}})
    site = out["result"]["sites"][0]
    assert site["volume_m3_per_year"] == pytest.approx(100 * 1.6 * 0.8 * 0.85, abs=0.1)
    assert site["location_class"] == "outside"
    assert any("first-flush" in f for f in site["flags"])
    assert out["result"]["roofs_for_10pct"] >= 1
    assert out["result"]["rain"]["source"] == "entered by the user"


def test_di_site_inside_likely_zone_counts_most():
    square = lambda d: Point(78.556, 29.92).buffer(d)  # noqa: E731
    b = {"result": {"geology": {"rock_class": "Quartzite"}},
         "_zones": {"small": square(0.0005), "likely": square(0.001), "large": square(0.002), "catchment": square(0.003),
                    "dem": None, "spring_elevation_m": None}}
    sites = [{"id": "in", "latitude": 29.92, "longitude": 78.556, "roof_area_m2": 100, "first_flush": True, "filter": True},
             {"id": "wide", "latitude": 29.9215, "longitude": 78.556, "roof_area_m2": 100, "first_flush": True, "filter": True}]
    out = module_c.estimate({"spring": NAULI, "field": {"lean_flow_lpm": 2}, "di": {"sites": sites, "assumptions": {"annual_rain_mm": 1600}}},
                            b_output=b)
    inside, wide = out["result"]["sites"]
    assert inside["location_class"] == "inside_likely" and wide["location_class"] == "inside_large"
    assert inside["added_flow_lpm_lean"]["mid"] > wide["added_flow_lpm_lean"]["mid"] > 0
    lean_minutes = 5 * module_c.DAYS_PER_MONTH * 1440
    assert inside["added_flow_lpm_lean"]["mid"] == pytest.approx(108.8 * 0.6 * 1000 / lean_minutes, abs=0.001)
    assert out["result"]["totals"]["pct_of_lean_flow"]["mid"] > 0


def test_bad_assumption_is_ignored_with_a_warning():
    out = module_c.estimate({"spring": NAULI, "field": {}, "di": {"sites": [], "assumptions": {"annual_rain_mm": 1600,
                                                                                                "collection_coefficient": 7}}})
    assert any("collection_coefficient" in w for w in out["warnings"])
    assert out["result"]["assumptions"][1]["value"] == 0.8


def test_request_checks():
    with pytest.raises(ValueError):
        server.clean_request({"spring": {"latitude": 12.9, "longitude": 77.6}})  # outside the hills covered
    with pytest.raises(ValueError):
        server.clean_request({"spring": {"latitude": "x", "longitude": 78}})
    spring, field, di = server.clean_request({"spring": {"latitude": 29.9, "longitude": 78.5}, "field": {"dip_angle_deg": "30", "households": ""}})
    assert field == {"dip_angle_deg": 30.0} and di == {}
    assert server.finite({"a": [float("nan"), 1.0, np.float64(2)]}) == {"a": [None, 1.0, 2.0]}


def test_page_questions_match_module_a():
    """app/src/questions.ts must use Module A's ids and allowed values."""
    import module_a_vulnerability as module_a
    text = (ROOT / "app" / "src" / "questions.ts").read_text(encoding="utf-8")
    page = {}
    for block in re.split(r"\n  \{ ", text)[1:]:
        found = re.match(r"id: '(\w+)'", block)
        if not found:
            continue
        kind = re.search(r"kind: '(\w+)'", block).group(1)
        page[found.group(1)] = (kind, re.findall(r"\['(\w+)', '", block))
    scored = {k: v for k, v in module_a.OPTIONAL.items() if v[0] != "text"}
    assert set(scored) <= set(page)
    for question_id, (kind, values) in page.items():
        if question_id in scored:
            assert kind == scored[question_id][0]
            if kind == "choice":
                assert values == scored[question_id][1]


@pytest.mark.skipif(not HAS_DEM, reason="Copernicus DEM tile for Nauli Dhara not in the layer cache")
def test_full_assessment_of_nauli_dhara():
    tool = server.Tool()
    sites = [{"id": "s1", "latitude": 29.9185, "longitude": 78.5556, "roof_area_m2": 100, "first_flush": True, "filter": True}]
    response = tool.assess({"spring": NAULI, "field": {"flow_vs_past": "a_bit_less", "lean_flow_lpm": 2.5, "monsoon_flow_lpm": 12},
                            "di": {"sites": sites}})
    a, b, c = response["A"], response["B"], response["C"]
    assert a["result"]["class"] in {"Low", "Medium", "High"}
    zones = {z["scenario"]: z["area_ha"] for z in b["result"]["zones"]}
    assert zones["small"] <= zones["likely"] <= zones["large"]
    assert b["result"]["potential_overlay"]["image"].startswith("data:image/png;base64,")
    assert len(b["result"]["recharge_spots"]) <= 3 and b["result"]["surface_catchment"]["area_ha"] > 0
    assert "_zones" not in b
    assert {"needed", "reason", "candidates", "checks"} <= set(b["result"]["detached"])
    assert [r["radius_m"] for r in a["result"]["map"]["rings"]] == [500, 1000]
    assert c["result"]["sites"][0]["location_class"] in module_c.SHARE
    import json
    json.dumps(response, allow_nan=False)
    assert (server.RUNS / response["run_id"] / "report.md").is_file()

"""Module C: best-case impact of DI (direct injection) recharge on a spring.

DI sends rooftop rainwater down a defunct handpump into the aquifer. There is no before/after DI measurement in
any of our data, so nothing can be trained; this is transparent water-balance arithmetic with every assumption
shown (docs: Project1 plan, section 4.5). The numbers are upper bounds to plan and monitor against, not predictions.

For each DI site:
- Water injected per year  V = roof area x annual rain x collection coefficient x injection efficiency.
- Share that reaches the spring. Set by where the site sits relative to Module B's zones: inside the likely zone
  most of it can, inside the large zone some, elsewhere in the surface catchment little, below the spring none.
  These shares are judgement (low / mid / best case), to be replaced by monitoring.
- Added spring flow. Spread over the whole year (annual average), or, best case, all coming out in the lean season.
- Water-level rise near the handpump after the wettest month: injected volume / (circle of influence x specific
  yield). A temporary mound, not a lasting rise.
- Travel time to the spring: distance / (K x gradient / effective porosity), with wide hard-rock ranges for K;
  an order of magnitude only.

Usage: called by the tool server (scripts/spring_tool_server.py) after Modules A and B. Its inputs follow
docs/module-contract.md plus "di": {"sites": [...], "assumptions": {...}}.
"""

from __future__ import annotations

import math
import statistics


MINUTES_PER_YEAR = 525_600
DAYS_PER_MONTH = 30.44
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

DEFAULTS = {"annual_rain_mm": None, "collection_coefficient": 0.8, "injection_efficiency": 0.85,
            "lean_season_months": 5, "radius_of_influence_m": 50}
LIMITS = {"collection_coefficient": (0.3, 1.0), "injection_efficiency": (0.3, 1.0), "lean_season_months": (1, 12),
          "radius_of_influence_m": (5, 500), "annual_rain_mm": (100, 6000)}

# Share of a site's injected water that can reach the spring: (low, mid, best case). Judgement, to be replaced by monitoring.
SHARE = {
    "inside_likely": (0.3, 0.6, 1.0),
    "inside_large": (0.1, 0.3, 0.6),
    "in_catchment": (0.05, 0.15, 0.3),
    "outside": (0.0, 0.02, 0.1),
    "below_spring": (0.0, 0.0, 0.0),
}
LOCATION_NOTE = {
    "inside_likely": "Inside the likely recharge zone: most of the injected water can reach this spring.",
    "inside_large": "Inside the large zone only: some of the water may reach this spring.",
    "in_catchment": "In the surface catchment but outside the recharge zones: little of the water is likely to reach this spring.",
    "outside": "Outside the spring's catchment and recharge zones: the water will mostly feed other springs or streams.",
    "below_spring": "Lower than the spring outlet: water injected here cannot feed this spring.",
}
# Specific yield (also used as effective porosity) and hydraulic conductivity (m/day) ranges by rock.
# Hard-rock values follow the 0.5-3 % used for fractured Himalayan rocks (CGWB GEC-2015 norms, to confirm with WATSAN).
AQUIFER = {
    "hard rock": {"sy": (0.005, 0.03), "k": (0.05, 5.0)},
    "carbonate": {"sy": (0.01, 0.05), "k": (0.5, 50.0)},
    "alluvium / debris": {"sy": (0.08, 0.16), "k": (1.0, 30.0)},
}
BENCHMARKS = [
    "ICIMOD reports +23% and +48% average spring flow after full springshed treatment (trenches, pits, plantation over the "
    "whole recharge area) at two Indian Himalayan pilot springs. DI at a few handpumps should add well below that unless roofs are large.",
    "RDI's handpump design collects about 70-80% of roof rain. A 100 m2 roof under 1,600 mm of rain injects about 100-110 m3 a year.",
]
MONITORING = [
    "Measure the spring every month on a fixed date: three bucket-and-stopwatch readings, and note the weather of the last 3 days.",
    "Start before the DI works if at all possible, so there is a baseline year to compare with.",
    "Read the water level in each DI handpump with a dip meter weekly in the monsoon and monthly otherwise.",
    "Keep a rain gauge in the village and log each DI injection (date, roof, rough volume).",
    "Measure one nearby spring without DI the same way as a control, so a wet or dry year is not mistaken for the DI effect.",
    "Test water quality (turbidity, coliform, iron) at the spring before and after the first monsoon of injection.",
]


def _number(value):
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _range(low, mid, high, digits=2):
    return {"low": round(low, digits), "mid": round(mid, digits), "high": round(high, digits)}


def aquifer_for(rock_text):
    text = (rock_text or "").lower()
    if "alluvium" in text or "debris" in text:
        return "alluvium / debris"
    if "carbonate" in text and "mixed" not in text:
        return "carbonate"
    return "hard rock"


def rainfall(features, layers, lon, lat, override):
    """Annual rain (mm) with its source, and the monthly pattern (CHIRPS 2018-2025 mean, scaled to that annual total)."""
    monthly = None
    if layers is not None and getattr(layers, "pcp_m", None) is not None:
        values = []
        for m in range(1, 13):
            v = [layers.pcp_m.sample(f"{y}-{m:02d}", lon, lat) for y in range(2018, 2026)]
            v = [x for x in v if not math.isnan(x)]
            values.append(statistics.fmean(v) if v else float("nan"))
        if not any(math.isnan(v) for v in values) and sum(values) > 0:
            monthly = values
    if override:
        annual, source = float(override), "entered by the user"
    elif features.get("rain_imd_mean_annual_mm"):
        annual = float(features["rain_imd_mean_annual_mm"])
        source = f"IMD gridded rain gauges, mean of {features.get('rain_imd_years_used', '2001-2025')}"
    elif features.get("rain_chirps_mean_annual_mm_2018_2025"):
        annual = float(features["rain_chirps_mean_annual_mm_2018_2025"])
        source = ("CHIRPS satellite estimate, 2018-2025 mean. In these hills CHIRPS reads about 45% above the IMD gauges, "
                  "so this may be optimistic; add the IMD files or enter a local value")
    elif monthly:
        annual, source = sum(monthly), "CHIRPS monthly, 2018-2025 mean"
    else:
        return None
    if monthly:
        total = sum(monthly)
        monthly = [round(v * annual / total, 1) for v in monthly]
    return {"annual_mm": round(annual), "source": source, "monthly_mm": monthly}


def site_elevation(lat, lon, dem, mod, layers):
    if dem is not None:
        z, t = dem
        row, col = mod.centre_index(t, lon, lat)
        if 0 <= row < z.shape[0] and 0 <= col < z.shape[1] and z[row, col] > -1000:
            return float(z[row, col])
    if layers is not None:
        z, t = mod.read_window(layers.dem, lon, lat, 60)
        if z is not None:
            row, col = mod.centre_index(t, lon, lat)
            if 0 <= row < z.shape[0] and 0 <= col < z.shape[1] and z[row, col] > -1000:
                return float(z[row, col])
    return None


def estimate(inputs, session=None, features=None, b_output=None):
    """Module C under the shared contract. inputs: {"spring", "field", "di": {"sites", "assumptions"}}.
    session: Module A's LayerSession (rain pattern, site elevations); features: the layer values at the spring;
    b_output: Module B's output including its "_zones" (shapely zones, the DEM window and the spring elevation)."""
    from shapely.geometry import Point

    spring = inputs["spring"]
    lat, lon = float(spring["latitude"]), float(spring["longitude"])
    name = spring.get("name") or f"{lat:.5f}, {lon:.5f}"
    field = inputs.get("field") or {}
    di = inputs.get("di") or {}
    sites = di.get("sites") or []
    features = features or {}
    warnings, rationale, missing = [], [], []

    assumptions = dict(DEFAULTS)
    for key, value in (di.get("assumptions") or {}).items():
        if key in DEFAULTS and value not in (None, ""):
            v = _number(value)
            lo, hi = LIMITS[key]
            if v is None or not lo <= v <= hi:
                warnings.append(f"Assumption ignored: {key} = {value!r} (allowed {lo}-{hi}).")
                continue
            assumptions[key] = v
    layers = getattr(session, "layers", None) if session is not None else None
    mod = getattr(session, "mod", None)
    rain = rainfall(features, layers, lon, lat, assumptions["annual_rain_mm"])
    base = {"module": "C", "title": "Potential impact of DI recharge", "version": "v1 draft",
            "spring": {"name": name, "latitude": lat, "longitude": lon, "elevation_m": spring.get("elevation_m")}}
    if rain is None:
        return {**base, "status": "unavailable", "result": None, "confidence": "Low",
                "rationale": ["No rainfall value was found for this location. Enter the yearly rainfall under the DI assumptions."],
                "missing_inputs": [{"id": "annual_rain_mm", "indicator": "Yearly rainfall", "needs": "A yearly rainfall value in mm."}],
                "warnings": warnings, "report_markdown": f"# DI impact: {name}\n\nNo rainfall value was found.\n"}

    zones = (b_output or {}).get("_zones") or {}
    b_result = (b_output or {}).get("result") or {}
    spring_z = zones.get("spring_elevation_m") or _number(spring.get("elevation_m"))
    rock_text = ((b_result.get("geology") or {}).get("rock_class")) or field.get("rock_at_outlet") or ""
    aquifer = aquifer_for(rock_text)
    sy, k = AQUIFER[aquifer]["sy"], AQUIFER[aquifer]["k"]
    if not zones:
        warnings.append("No recharge zone was available from the springshed section, so every site is treated as outside it.")
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * math.radians(lat))
    m_per_deg_lon = 111412.84 * math.cos(math.radians(lat))
    rain_m = rain["annual_mm"] / 1000
    cc, eff = assumptions["collection_coefficient"], assumptions["injection_efficiency"]
    lean_months = assumptions["lean_season_months"]
    lean_minutes = lean_months * DAYS_PER_MONTH * 1440
    radius = assumptions["radius_of_influence_m"]
    wettest_share = max(rain["monthly_mm"]) / rain["annual_mm"] if rain["monthly_mm"] else 0.25

    results, monthly_total = [], [0.0] * 12
    for i, s in enumerate(sites):
        try:
            s_lat, s_lon = float(s["latitude"]), float(s["longitude"])
            roof = float(s.get("roof_area_m2") or 0)
        except (KeyError, TypeError, ValueError):
            warnings.append(f"DI site {i + 1} was skipped: it needs a latitude, longitude and roof area.")
            continue
        if roof <= 0 or roof > 5000:
            warnings.append(f"DI site {s.get('name') or i + 1} was skipped: roof area must be between 1 and 5,000 m2.")
            continue
        site_id = str(s.get("id") or f"site-{i + 1}")
        label = s.get("name") or f"DI site {i + 1}"
        point = Point(s_lon, s_lat)
        z = site_elevation(s_lat, s_lon, zones.get("dem"), mod, layers) if mod else None
        height = None if z is None or spring_z is None else z - spring_z
        distance = math.hypot((s_lat - lat) * m_per_deg_lat, (s_lon - lon) * m_per_deg_lon)
        if height is not None and height < -3:
            where = "below_spring"
        elif any(zones.get(sc) is not None and zones[sc].contains(point) for sc in ("small", "likely")):
            where = "inside_likely"
        elif zones.get("large") is not None and zones["large"].contains(point):
            where = "inside_large"
        elif zones.get("catchment") is not None and zones["catchment"].contains(point):
            where = "in_catchment"
        else:
            where = "outside"
        volume = roof * rain_m * cc * eff
        share = SHARE[where]
        annual = [volume * f * 1000 / MINUTES_PER_YEAR for f in share]
        lean = [volume * f * 1000 / lean_minutes for f in share]
        peak_month = volume * wettest_share
        rise = (peak_month / (math.pi * radius ** 2 * sy[1]), peak_month / (math.pi * radius ** 2 * sy[0]))
        travel = None
        if height is not None and height > 0 and distance > 0:
            gradient = max(height / distance, 0.02)
            travel = {"low": round(distance * sy[0] / (k[1] * gradient), 1), "high": round(distance * sy[1] / (k[0] * gradient))}
        flags = []
        if not s.get("first_flush"):
            flags.append("No first-flush diverter: the first dirty roof water goes straight into the drinking-water aquifer.")
        if not s.get("filter"):
            flags.append("No filter: silt can clog the handpump and reach the spring.")
        if roof > 300:
            flags.append("Large roof: check the handpump can take the peak monsoon inflow without overflowing.")
        if where in ("outside", "below_spring"):
            flags.append("Consider moving this site uphill into the likely recharge zone.")
        if distance > 2000:
            flags.append("More than 2 km from the spring.")
        if rain["monthly_mm"]:
            for m in range(12):
                monthly_total[m] += roof * rain["monthly_mm"][m] / 1000 * cc * eff
        results.append({
            "id": site_id, "name": label, "latitude": s_lat, "longitude": s_lon,
            "elevation_m": None if z is None else round(z), "roof_area_m2": roof,
            "volume_m3_per_year": round(volume, 1), "location_class": where, "location_note": LOCATION_NOTE[where],
            "share_reaching_spring": _range(*share), "added_flow_lpm_annual": _range(*annual, digits=3),
            "added_flow_lpm_lean": _range(*lean, digits=3),
            "water_level_rise_m": {"low": round(rise[0], 2), "high": round(rise[1], 2)},
            "travel_time_days": travel, "distance_to_spring_m": round(distance),
            "height_above_spring_m": None if height is None else round(height), "flags": flags,
        })

    lean_flow = _number(field.get("lean_flow_lpm"))
    total_volume = sum(r["volume_m3_per_year"] for r in results)
    tot_annual = _range(*(sum(r["added_flow_lpm_annual"][x] for r in results) for x in ("low", "mid", "high")), digits=3)
    tot_lean = _range(*(sum(r["added_flow_lpm_lean"][x] for r in results) for x in ("low", "mid", "high")), digits=3)
    pct = None
    if lean_flow and lean_flow > 0 and results:
        pct = _range(*(100 * tot_lean[x] / lean_flow for x in ("low", "mid", "high")), digits=1)
    one_roof = 100 * rain_m * cc * eff * SHARE["inside_likely"][1] * 1000 / lean_minutes
    roofs_for_10pct = math.ceil(0.1 * lean_flow / one_roof) if lean_flow and lean_flow > 0 else None

    if results:
        inside = sum(1 for r in results if r["location_class"] == "inside_likely")
        rationale.append(f"{len(results)} DI {'site' if len(results) == 1 else 'sites'} with {sum(r['roof_area_m2'] for r in results):,.0f} m2 of roof can inject about "
                         f"{total_volume:,.0f} m3 ({total_volume * 1000:,.0f} litres) a year at {rain['annual_mm']:,} mm of rain.")
        rationale.append(f"{inside} of {len(results)} {'lies' if inside == 1 else 'lie'} inside the likely recharge zone. Counting only the share that can reach the spring, "
                         f"the spring could gain {tot_lean['mid']:.2f} L/min in the lean season (range {tot_lean['low']:.2f}-{tot_lean['high']:.2f}), "
                         f"if all of it comes out then; spread over the year it is {tot_annual['mid']:.2f} L/min.")
        if pct:
            rationale.append(f"That is about {pct['mid']:.0f}% of the present lean-season flow of {lean_flow:g} L/min "
                             f"(range {pct['low']:.0f}-{pct['high']:.0f}%).")
        rationale.append("The water level near each handpump may rise for a while after the wettest month (shown per site); "
                         "it falls back as the water spreads through the rock.")
    else:
        rationale.append("No DI sites were placed yet. Add them on the map to see what they would add.")
    if roofs_for_10pct:
        rationale.append(f"To add 10% to the lean flow ({0.1 * lean_flow:.2f} L/min), about {roofs_for_10pct} {'roof' if roofs_for_10pct == 1 else 'roofs'} of 100 m2 inside the likely zone would be needed (mid case).")
    if not lean_flow:
        missing.append({"id": "lean_flow_lpm", "indicator": "Lean-season flow",
                        "needs": "A May-June bucket reading turns the added flow into a % of what the spring gives now."})
    if not zones:
        missing.append({"id": "springshed", "indicator": "Recharge zone", "needs": "The springshed section must run to place the sites."})

    benchmarks = [f"One 100 m2 roof inside the likely zone adds about {one_roof:.2f} L/min to the lean-season flow (mid case)."] + BENCHMARKS
    assumption_rows = [
        {"id": "annual_rain_mm", "label": "Yearly rain", "value": rain["annual_mm"], "unit": "mm", "note": rain["source"]},
        {"id": "collection_coefficient", "label": "Roof rain collected", "value": cc, "unit": "share", "note": "RDI design 0.7-0.8 for metal or concrete roofs."},
        {"id": "injection_efficiency", "label": "Kept after first flush and overflow", "value": eff, "unit": "share", "note": "Assumed 0.8-0.9."},
        {"id": "share", "label": "Share reaching the spring", "value": "0.3-1.0 inside the likely zone; 0.1-0.6 large zone; up to 0.3 elsewhere in the catchment",
         "unit": "share", "note": "Judgement until monitoring data exist."},
        {"id": "lean_season_months", "label": "Lean season", "value": lean_months, "unit": "months", "note": "Best case: all extra water comes out in these months."},
        {"id": "specific_yield", "label": "Specific yield of the rock", "value": f"{sy[0] * 100:g}-{sy[1] * 100:g}", "unit": "%",
         "note": f"{aquifer.capitalize()} ({rock_text or 'rock not known'}). CGWB GEC-2015 norms, to confirm with WATSAN."},
        {"id": "radius_of_influence_m", "label": "Mound radius around the handpump", "value": radius, "unit": "m", "note": "Unknown; 20-150 m is plausible."},
        {"id": "conductivity", "label": "Rock permeability (K)", "value": f"{k[0]:g}-{k[1]:g}", "unit": "m/day", "note": "Wide range for fractured rock; travel times are an order of magnitude only."},
    ]
    result = {
        "rain": rain, "sites": results,
        "totals": {"volume_m3_per_year": round(total_volume, 1), "added_flow_lpm_annual": tot_annual,
                   "added_flow_lpm_lean": tot_lean, "lean_flow_lpm": lean_flow, "pct_of_lean_flow": pct},
        "monthly_injection_m3": [round(v, 1) for v in monthly_total] if rain["monthly_mm"] and results else None,
        "roofs_for_10pct": roofs_for_10pct, "assumptions": assumption_rows,
        "benchmarks": benchmarks, "monitoring_plan": MONITORING,
    }
    return {**base, "status": "provisional", "result": result, "confidence": "Low", "rationale": rationale,
            "missing_inputs": missing, "warnings": warnings, "report_markdown": report_markdown(name, result, rationale, warnings)}


def report_markdown(name, result, rationale, warnings):
    lines = [f"# Potential impact of DI recharge: {name}", "", "Best-case water balance, not a prediction (Module C v1 draft).", "",
             "## Summary", *(f"- {r}" for r in rationale), ""]
    if result["sites"]:
        lines += ["| Site | Where | Water injected (m3/yr) | Added lean flow (L/min, low-mid-best) | Water-level rise (m) |", "|---|---|---|---|---|"]
        for s in result["sites"]:
            f = s["added_flow_lpm_lean"]
            lines.append(f"| {s['name']} | {s['location_class'].replace('_', ' ')} | {s['volume_m3_per_year']:.0f} | "
                         f"{f['low']:.2f} - {f['mid']:.2f} - {f['high']:.2f} | {s['water_level_rise_m']['low']:.1f}-{s['water_level_rise_m']['high']:.1f} |")
        lines.append("")
    lines += ["## Assumptions", *(f"- {a['label']}: {a['value']} {a['unit']} ({a['note']})" for a in result["assumptions"]), "",
              "## Monitoring plan", *(f"- {m}" for m in result["monitoring_plan"]), ""]
    if warnings:
        lines += ["## Notes", *(f"- {w}" for w in warnings), ""]
    return "\n".join(lines)

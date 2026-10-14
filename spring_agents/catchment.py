"""AG-CAT: preserve point/outlet distinction and gate unresolved delineation."""

from __future__ import annotations

import math

from .storage import RunStore


def mask_area(mask: list[list[bool | None]], cell_width_m: float, cell_height_m: float) -> dict:
    """R-CAT-03/04 mechanical arithmetic for an already approved metric-grid mask.

    This does not create a mask, validate a polygon, or approve a routing method.
    """
    if (not mask or not mask[0] or not all(len(row) == len(mask[0]) for row in mask)
            or any(type(value) not in (bool, type(None)) for row in mask for value in row)):
        raise ValueError("Mask must be a nonempty rectangular boolean/null grid")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0
               for value in (cell_width_m, cell_height_m)):
        raise ValueError("Metric cell dimensions must be positive finite numbers")
    rows, columns = len(mask), len(mask[0])
    included = sum(value is True for row in mask for value in row)
    edge = any(mask[0][c] is True or mask[rows - 1][c] is True for c in range(columns)) or any(
        mask[r][0] is True or mask[r][columns - 1] is True for r in range(rows))
    voids = any(value is None for row in mask for value in row)
    area_m2 = included * float(cell_width_m) * float(cell_height_m)
    return {"included_cells": included, "area_m2": area_m2, "area_ha": area_m2 / 10_000,
            "touches_grid_edge": edge, "grid_contains_nodata": voids,
            "passes_edge_and_void_screen": bool(included and not edge and not voids)}


def run(store: RunStore) -> None:
    location = store.get("AG-SPR.location_evidence")
    point = location["payload"].get("processing_point") if location else None
    store.emit("AG-CAT.outlet_decision", "provisional" if point else "unavailable",
               "Original spring point retained; no outlet adjustment policy approved" if point else "No valid spring point",
               payload={"spring_point": point, "selected_surface_outlet": None,
                        "adjustment_distance_m": None, "outlet_policy": "pending review"},
               upstream=["AG-SPR.location_evidence", "AG-TER.terrain_coverage"], rule_ids=["R-CAT-01"],
               crs="EPSG:4326" if point else None)
    reason = "No approved routing, outlet-selection and DEM-processing configuration; surface polygon unavailable"
    for name, rules in [
        ("drainage_network", ["R-CAT-02"]),
        ("catchment_geometry", ["R-CAT-02"]),
        ("catchment_sensitivity", ["R-CAT-05"]),
    ]:
        store.emit(f"AG-CAT.{name}", "unavailable", reason,
                   upstream=["AG-SPR.location_evidence", "AG-TER.terrain_package", "AG-TER.terrain_coverage", "AG-CAT.outlet_decision"],
                   rule_ids=rules, payload={"hydrogeological_validation": "not assessed"})

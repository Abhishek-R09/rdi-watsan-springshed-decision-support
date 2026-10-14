"""AG-VER: mechanical checks with explicit not-assessed scientific validation."""

from __future__ import annotations

from .storage import RunStore


def run(store: RunStore) -> None:
    location = store.get("AG-SPR.location_evidence")
    terrain = store.get("AG-TER.terrain_package")
    polygon = store.get("AG-CAT.catchment_geometry")
    trace = store.get("AG-LIN.run_trace")
    lineage_issues = store.get("AG-LIN.lineage_issues")["payload"]["issues"]
    checks = [
        {"check": "coordinate_validity", "status": "passed" if location["status"] == "complete" else "failed",
         "reason": location["reason"]},
        {"check": "lineage_links", "status": "failed" if lineage_issues else "passed",
         "reason": lineage_issues or "All recorded links resolved"},
        {"check": "approved_dem_and_routing", "status": "not assessed" if terrain["status"] == "unavailable" else "pending",
         "reason": terrain["reason"]},
        {"check": "polygon_geometry_area_crs", "status": "not assessed" if polygon["status"] == "unavailable" else "pending",
         "reason": "No generated polygon available" if polygon["status"] == "unavailable" else "Independent geometry check not implemented"},
        {"check": "hydrogeological_boundary_validation", "status": "not assessed",
         "reason": "No independently verified reference boundary supplied"},
    ]
    # A pending check cannot release a scientific result as if verified.
    blocking = [item for item in checks if item["status"] in {"failed", "pending"}]
    released = polygon["status"] in {"complete", "provisional"} and not blocking
    common = ["AG-ORC.assessment_manifest", "AG-LIN.run_trace", "AG-LIN.lineage_issues",
              "AG-SPR.location_evidence", "AG-TER.terrain_package", "AG-CAT.catchment_geometry", "AG-CAT.outlet_decision"]
    store.emit("AG-VER.verification_report", "provisional" if blocking or not released else "complete",
               "Mechanical checks recorded; boundary accuracy not assessed",
               payload={"checks": checks, "lineage_trace_id": trace["output_id"]},
               upstream=common, rule_ids=["R-VER-01", "R-VER-02"], issues=lineage_issues)
    store.emit("AG-VER.release_status", "complete", "Per-output availability determined",
               payload={"AG-CAT.catchment_geometry": "released" if released else "unavailable",
                        "reason": None if released else polygon["reason"],
                        "hydrogeological_validation": "not assessed"},
               upstream=["AG-VER.verification_report"], rule_ids=["R-VER-01", "R-VER-02"])
    store.emit("AG-VER.unresolved_checks", "complete", "Unperformed checks retained",
               payload={"checks": [item for item in checks if item["status"] != "passed"]},
               upstream=["AG-VER.verification_report"], rule_ids=["R-VER-02"])

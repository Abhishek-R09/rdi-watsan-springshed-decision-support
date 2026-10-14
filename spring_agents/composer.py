"""AG-COM: explain recorded results without adding analytical claims."""

from __future__ import annotations

from .storage import RunStore


def run(store: RunStore) -> None:
    point = store.get("AG-SPR.location_evidence")["payload"].get("processing_point")
    outlet = store.get("AG-CAT.outlet_decision")["payload"].get("selected_surface_outlet")
    polygon = store.get("AG-CAT.catchment_geometry")
    release = store.get("AG-VER.release_status")["payload"]
    trace = store.get("AG-LIN.run_trace")
    issues = store.get("AG-LIN.lineage_issues")["payload"]["issues"]
    snapshot = store.get("AG-ORC.source_selection")["payload"]
    mode = store.get("AG-ORC.run_context")["payload"]["mode"]
    released = release.get("AG-CAT.catchment_geometry") == "released"
    common = ["AG-ORC.assessment_manifest", "AG-LIN.contract_map", "AG-LIN.run_trace",
              "AG-LIN.lineage_issues", "AG-VER.verification_report", "AG-VER.release_status",
              "AG-CAT.catchment_geometry", "AG-CAT.outlet_decision", "AG-SPR.spring_profile"]
    store.emit("AG-COM.assessment_summary", "provisional" if released else "unavailable",
               "Surface catchment presented with source and uncertainty" if released else "Surface catchment unavailable; input and gaps retained",
               payload={"spring_id": store.get("AG-SPR.spring_profile")["payload"].get("spring_id"),
                        "surface_catchment": polygon["payload"] if released else None,
                        "surface_catchment_status": release.get("AG-CAT.catchment_geometry"),
                        "surface_catchment_reason": release.get("reason"),
                        "springshed_status": "unavailable" if mode == "springshed" else "not scheduled",
                        "label": "DEM-derived surface catchment; groundwater recharge area unverified" if released else None,
                        "area_m2": polygon["payload"].get("area_m2") if released else None,
                        "area_ha": polygon["payload"].get("area_ha") if released else None,
                        "snapshot_id": snapshot.get("snapshot_id"),
                        "lineage_trace_id": trace["output_id"], "lineage_issues": issues,
                        "hydrogeological_validation": "not assessed",
                        "next_field_check": "Confirm the spring point and potential outlet with WATSAN; review terrain and geology before treating any surface boundary as recharge."},
               upstream=common, rule_ids=["R-COM-01", "R-COM-02"], issues=issues,
               snapshot_id=snapshot.get("snapshot_id"))
    features = [{"feature_id": "submitted_spring", "type": "Point", "coordinates": point,
                 "status": "supplied" if point else "unavailable"}]
    if outlet:
        features.append({"feature_id": "selected_surface_outlet", "type": "Point", "coordinates": outlet,
                         "status": "selected"})
    if released:
        features.append({"feature_id": "surface_catchment", "type": "Polygon",
                         "geometry": polygon["payload"].get("geometry"), "status": "provisional",
                         "label": "DEM-derived surface catchment; groundwater recharge area unverified"})
    store.emit("AG-COM.map_layer_manifest", "complete", "Available map features listed",
               payload={"features": features, "basemap_role": "display only"},
               upstream=["AG-SPR.location_evidence", "AG-CAT.outlet_decision", "AG-CAT.catchment_geometry", "AG-VER.release_status"],
               rule_ids=["R-COM-01"])
    store.emit("AG-COM.export_manifest", "complete", "Existing versioned output files enumerated",
               payload={"records": [{"output_id": key, "record_sha256": value["record_sha256"]} for key, value in store.records.items()],
                        "lineage_trace_id": trace["output_id"], "verification_report_id": "AG-VER.verification_report"},
               upstream=["AG-COM.assessment_summary", "AG-COM.map_layer_manifest", "AG-LIN.run_trace", "AG-VER.verification_report"],
               rule_ids=["R-COM-02"])

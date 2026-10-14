"""AG-TER: validate a locally approved DEM snapshot; never fetch on request."""

from __future__ import annotations

import json
from pathlib import Path

from .specs import ROOT
from .storage import RunStore, checksum


ACTIVE = ROOT / "data/02_processed/snapshots/active.json"


def select_snapshot(point: dict | None) -> tuple[dict | None, list[str]]:
    issues = []
    if point is None:
        return None, ["R-ORC-02: no valid processing point"]
    if not ACTIVE.is_file():
        return None, [f"R-ORC-02: approved active snapshot missing: {ACTIVE.relative_to(ROOT)}"]
    try:
        snapshot = json.loads(ACTIVE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, [f"R-ORC-02: active snapshot unreadable: {exc}"]
    if snapshot.get("approval_status") != "approved" or not snapshot.get("snapshot_id"):
        return None, ["R-ORC-02: snapshot lacks recorded approval or ID"]
    dem = snapshot.get("dem") or {}
    if dem.get("source_id") not in {"SRC-018", "SRC-022"}:
        return None, ["R-ORC-02: approved snapshot has no SRC-018 or reviewed SRC-022 DEM"]
    if dem.get("source_id") == "SRC-022" and dem.get("review_status") != "approved":
        return None, ["R-ORC-02: SRC-022 has no recorded product-specific review"]
    bounds = dem.get("coverage_bbox_wgs84")
    if not isinstance(bounds, list) or len(bounds) != 4:
        return None, ["R-ORC-02: DEM coverage bounds are missing"]
    try:
        west, south, east, north = map(float, bounds)
        if not (west <= point["longitude"] <= east and south <= point["latitude"] <= north):
            return None, ["R-ORC-02: spring point outside DEM coverage"]
    except (ValueError, TypeError, KeyError):
        return None, ["R-ORC-02: DEM coverage bounds are invalid"]
    paths = dem.get("tiles")
    if not isinstance(paths, list) or not paths:
        return None, ["R-TER-01: DEM tile list is empty"]
    if not isinstance(dem.get("transformation_ids"), list):
        return None, ["R-ORC-02: DEM snapshot must name applied transformation IDs or an explicit empty list"]
    for tile in paths:
        relative = tile.get("relative_path", "")
        file = (ROOT / relative).resolve()
        if ROOT not in file.parents or not file.is_file():
            issues.append(f"R-TER-01: DEM tile unavailable: {relative}")
        elif checksum(file).lower() != str(tile.get("sha256", "")).lower():
            issues.append(f"R-TER-01: DEM checksum mismatch: {relative}")
    if issues:
        return None, issues
    return snapshot, []


def run(store: RunStore, snapshot: dict | None, issues: list[str]) -> None:
    source_refs = []
    snapshot_id = None
    if snapshot:
        snapshot_id = snapshot["snapshot_id"]
        source_refs = [{"source_id": snapshot["dem"]["source_id"], "release": snapshot["dem"].get("release"),
                        "tiles": snapshot["dem"]["tiles"],
                        "transformation_ids": snapshot["dem"]["transformation_ids"]}]
    store.emit("AG-TER.terrain_coverage", "provisional" if snapshot else "unavailable",
               "Declared DEM bounds and tile checksums checked; raster CRS, datum and no-data still unverified" if snapshot else "No usable approved local DEM",
               payload={"dem": snapshot.get("dem") if snapshot else None, "gaps": issues},
               upstream=["AG-ORC.source_selection", "AG-SPR.location_evidence"],
               source_refs=source_refs, rule_ids=["R-TER-01", "R-TER-04"], snapshot_id=snapshot_id, issues=issues)
    reason = "DEM routing and processing configuration require project approval" if snapshot else "DEM unavailable"
    for name, rules in [("terrain_package", ["R-TER-02", "R-TER-03"]),
                        ("terrain_derivatives", ["R-TER-03"])]:
        store.emit(f"AG-TER.{name}", "unavailable", reason,
                   upstream=["AG-TER.terrain_coverage"], source_refs=source_refs,
                   rule_ids=rules, snapshot_id=snapshot_id, issues=issues)

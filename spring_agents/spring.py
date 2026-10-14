"""AG-SPR: coordinate and field-evidence rules R-SPR-01 and R-SPR-03."""

from __future__ import annotations

import math
from datetime import datetime

from .storage import RunStore


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def validated_location(point: object) -> tuple[bool, float | None, float | None]:
    if not isinstance(point, dict):
        return False, None, None
    latitude, longitude = _number(point.get("latitude")), _number(point.get("longitude"))
    valid = (point.get("crs") == "EPSG:4326" and latitude is not None and longitude is not None
             and -90 <= latitude <= 90 and -180 <= longitude <= 180)
    return valid, latitude, longitude


def run(store: RunStore, submission: dict) -> None:
    point = submission.get("location")
    if not isinstance(point, dict):
        point = {}
    field_form = submission.get("field_form")
    if not isinstance(field_form, dict):
        field_form = {}
    crs = point.get("crs")
    valid, latitude, longitude = validated_location(point)
    issues = []
    if not valid:
        issues.append("R-SPR-01: location requires numeric WGS84 latitude/longitude and crs EPSG:4326; no coordinate transformation policy is approved")
    accuracy = _number(point.get("accuracy_m")) if "accuracy_m" in point else None
    if "accuracy_m" in point and (accuracy is None or accuracy < 0):
        issues.append("R-SPR-01: supplied accuracy_m is invalid; raw value retained")
    location = store.emit(
        "AG-SPR.location_evidence", "complete" if valid else "unavailable",
        "Original unshifted user point selected for raster lookup" if valid else "No defensible processing point",
        payload={"original": point, "processing_point": {"latitude": latitude, "longitude": longitude, "crs": crs} if valid else None,
                 "selection_reason": "one unambiguous user point; no outlet adjustment" if valid else None,
                 "accuracy_m": accuracy if accuracy is not None and accuracy >= 0 else None},
        upstream=["AG-ORC.run_context"], rule_ids=["R-SPR-01"], issues=issues, crs="EPSG:4326" if valid else None,
    )
    readings = field_form.get("bucket_readings", [])
    if not isinstance(readings, list):
        readings = []
        issues.append("R-SPR-03: bucket_readings must be an array")
    derived = []
    for index, reading in enumerate(readings):
        if not isinstance(reading, dict):
            issues.append(f"R-SPR-03: reading {index + 1} is not an object")
            continue
        volume, duration = _number(reading.get("volume_L")), _number(reading.get("time_s"))
        if volume is None or volume <= 0 or duration is None or duration <= 0:
            issues.append(f"R-SPR-03: reading {index + 1} needs positive volume_L and time_s")
            derived.append({"reading_index": index + 1, "original": reading, "discharge_L_min": None})
        else:
            derived.append({"reading_index": index + 1, "original": reading,
                            "discharge_L_min": volume * 60 / duration})
    good = sum(item["discharge_L_min"] is not None for item in derived)
    try:
        measured_at = datetime.fromisoformat(field_form.get("measurement_date_time", ""))
        date_valid = measured_at.tzinfo is not None
    except (TypeError, ValueError):
        date_valid = False
    context_complete = (date_valid and isinstance(field_form.get("measurement_conditions"), str)
                        and bool(field_form["measurement_conditions"].strip())
                        and isinstance(field_form.get("heavy_rainfall_recent"), bool))
    if good >= 3 and not context_complete:
        issues.append("R-SPR-03: three valid readings present but date/time, conditions or recent-rainfall context is missing")
    store.emit(
        "AG-SPR.spring_profile", "complete" if valid else "provisional",
        "User field evidence preserved; no unlocated historical spring record matched",
        payload={"spring_id": submission.get("spring_id"), "field_form": field_form,
                 "discharge_readings": derived,
                 "discharge_protocol": "protocol-recorded" if good >= 3 and context_complete else
                 ("context-incomplete" if good >= 3 else "insufficient-readings"),
                 "identity_match": "not assessed; no exact source locator supplied"},
        upstream=["AG-ORC.run_context", location["output_id"]], rule_ids=["R-SPR-02", "R-SPR-03"],
        issues=issues, units="L/min for calculated discharge",
    )
    store.emit("AG-SPR.field_evidence_issues", "complete", "Field evidence gaps recorded",
               payload={"issues": issues}, upstream=["AG-SPR.location_evidence", "AG-SPR.spring_profile"],
               rule_ids=["R-SPR-01", "R-SPR-02", "R-SPR-03"])

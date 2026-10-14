"""Reproducible data-quality audit for the processed spring master table."""

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "02_processed" / "spring_master" / "spring_master_v1.csv"
FEATURES = ROOT / "data" / "02_processed" / "spring_features" / "spring_features_v1.csv"
DICTIONARY = ROOT / "data" / "02_processed" / "spring_master" / "spring_master_v1_data_dictionary.csv"
FILL_SUMMARY = ROOT / "data" / "02_processed" / "spring_master" / "spring_master_v1_fill_summary.csv"
OUTPUT = ROOT / "data" / "03_outputs" / "validation" / "spring_master_v1_data_quality_audit.json"


def load_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def present(value):
    return value is not None and str(value).strip() != ""


def number(value):
    try:
        return float(value) if present(value) else None
    except (TypeError, ValueError):
        return None


def percent(numerator, denominator):
    return round(100 * numerator / denominator, 1) if denominator else None


def numeric_check(rows, column, low=None, high=None):
    filled = [number(row[column]) for row in rows if present(row.get(column, ""))]
    unparsable = sum(1 for row in rows if present(row.get(column, "")) and number(row[column]) is None)
    outside = [value for value in filled if (low is not None and value < low) or (high is not None and value > high)]
    return {
        "filled": len(filled),
        "unparsable": unparsable,
        "outside_expected_range": len(outside),
        "minimum": round(min(filled), 4) if filled else None,
        "maximum": round(max(filled), 4) if filled else None,
        "expected_range": [low, high],
    }


def main():
    rows = load_csv(MASTER)
    feature_rows = load_csv(FEATURES)
    dictionary_rows = load_csv(DICTIONARY)
    fill_rows = load_csv(FILL_SUMMARY)
    headers = list(rows[0])
    n = len(rows)

    ids = [row["record_id"] for row in rows]
    id_counts = Counter(ids)
    source_counts = Counter(row["source_dataset"] for row in rows)
    status_counts = Counter(row["coordinate_status"] for row in rows)

    coordinate_issues = []
    for row in rows:
        lat, lon = number(row["latitude"]), number(row["longitude"])
        status = row["coordinate_status"]
        valid_region = lat is not None and lon is not None and 28 <= lat <= 32 and 76 <= lon <= 82
        expected = "ok" if valid_region else ("missing" if lat is None or lon is None else "outside_study_region")
        if status != expected:
            coordinate_issues.append(row["record_id"])

    group_rows = defaultdict(list)
    for row in rows:
        if present(row["colocated_group_id"]):
            group_rows[row["colocated_group_id"]].append(row)
    group_size_mismatches = []
    primary_mismatches = []
    for group_id, members in group_rows.items():
        claimed = {row["colocated_group_size"] for row in members}
        primary_count = sum(row["is_primary_record"] == "Y" for row in members)
        if claimed != {str(len(members))}:
            group_size_mismatches.append(group_id)
        if primary_count != 1:
            primary_mismatches.append(group_id)

    values = {
        "elevation_m": (0, 9000),
        "slope_deg": (0, 90),
        "slope_mean_500m_deg": (0, 90),
        "tree_cover_500m_pct": (0, 100),
        "cropland_500m_pct": (0, 100),
        "built_up_500m_pct": (0, 100),
        "rainfall_mean_annual_mm": (0, 10000),
        "rainfall_cv_pct": (0, 200),
        "rainfall_monsoon_share_pct": (0, 100),
        "et0_mean_annual_mm": (0, 5000),
        "aridity_index": (0, 20),
        "soil_clay_pct": (0, 100),
        "soil_silt_pct": (0, 100),
        "soil_sand_pct": (0, 100),
        "soil_coarse_fragments_pct": (0, 100),
        "soil_bulk_density_g_cm3": (0.5, 2.5),
        "lineament_distance_m": (0, 100000),
        "gsi_fault_distance_m": (0, 100000),
        "gsi_fold_distance_m": (0, 100000),
        "ph": (0, 14),
        "tds_mg_l": (0, 100000),
        "discharge_lpm_low": (0, 100000),
        "discharge_lpm_high": (0, 100000),
        "recharge_area_ha_low": (0, 1000000),
        "recharge_area_ha_high": (0, 1000000),
    }
    numeric_checks = {column: numeric_check(rows, column, *bounds) for column, bounds in values.items()}

    relationship = {
        "soil_texture_sum_outside_98_to_102": 0,
        "land_cover_component_sum_over_100": 0,
        "discharge_low_greater_than_high": 0,
        "recharge_low_greater_than_high": 0,
        "imd_min_greater_than_mean": 0,
        "aridity_ratio_mismatch_over_0_01": 0,
    }
    for row in rows:
        texture = [number(row[column]) for column in ("soil_clay_pct", "soil_silt_pct", "soil_sand_pct")]
        if all(value is not None for value in texture) and not 98 <= sum(texture) <= 102:
            relationship["soil_texture_sum_outside_98_to_102"] += 1
        cover = [number(row[column]) for column in ("tree_cover_500m_pct", "cropland_500m_pct", "built_up_500m_pct")]
        if all(value is not None for value in cover) and sum(cover) > 100.01:
            relationship["land_cover_component_sum_over_100"] += 1
        discharge_low, discharge_high = number(row["discharge_lpm_low"]), number(row["discharge_lpm_high"])
        if discharge_low is not None and discharge_high is not None and discharge_low > discharge_high:
            relationship["discharge_low_greater_than_high"] += 1
        recharge_low, recharge_high = number(row["recharge_area_ha_low"]), number(row["recharge_area_ha_high"])
        if recharge_low is not None and recharge_high is not None and recharge_low > recharge_high:
            relationship["recharge_low_greater_than_high"] += 1
        imd_min, imd_mean = number(row["rainfall_imd_min_annual_mm"]), number(row["rainfall_imd_mean_annual_mm"])
        if imd_min is not None and imd_mean is not None and imd_min > imd_mean:
            relationship["imd_min_greater_than_mean"] += 1
        rain, et0, aridity = number(row["rainfall_mean_annual_mm"]), number(row["et0_mean_annual_mm"]), number(row["aridity_index"])
        if rain is not None and et0 not in (None, 0) and aridity is not None and abs((rain / et0) - aridity) > 0.01:
            relationship["aridity_ratio_mismatch_over_0_01"] += 1

    feature_by_id = {row["record_id"]: row for row in feature_rows}
    master_set, feature_set = set(ids), set(feature_by_id)
    common_columns = [column for column in headers if column in feature_rows[0]]
    changed_shared_values = Counter()
    for row in rows:
        original = feature_by_id.get(row["record_id"])
        if original:
            for column in common_columns:
                if row[column] != original[column]:
                    changed_shared_values[column] += 1

    dictionary_columns = {row["column"] for row in dictionary_rows}
    fill_by_column = {row["column"]: row for row in fill_rows}
    selected_fields = [
        "latitude", "elevation_m", "slope_deg", "land_cover_point", "rainfall_mean_annual_mm",
        "soil_clay_pct", "rock_class", "gsi_fault_distance_m", "gsi_fold_distance_m",
        "spring_type_class", "discharge_lpm_low", "ph", "tds_mg_l", "recharge_area_ha_low",
        "intervention_text",
    ]
    coverage = {field: fill_by_column[field] for field in selected_fields}

    audit = {
        "dataset": {"file": str(MASTER.relative_to(ROOT)).replace("\\", "/"), "rows": n, "columns": len(headers)},
        "identity_and_traceability": {
            "record_id_blank": sum(not present(value) for value in ids),
            "record_id_duplicate_values": sum(count > 1 for count in id_counts.values()),
            "source_dataset_blank": sum(not present(row["source_dataset"]) for row in rows),
            "source_dataset_counts": dict(source_counts),
            "dictionary_missing_columns": sorted(set(headers) - dictionary_columns),
            "dictionary_extra_columns": sorted(dictionary_columns - set(headers)),
            "master_only_ids": sorted(master_set - feature_set),
            "features_only_ids": sorted(feature_set - master_set),
            "shared_feature_columns_changed_in_master": dict(changed_shared_values),
        },
        "coordinates": {
            "status_counts": dict(status_counts),
            "status_value_mismatches": len(coordinate_issues),
            "valid_coordinate_records": sum(1 for row in rows if row["coordinate_status"] == "ok"),
            "low_precision_coordinate_records": sum(
                1 for row in rows if number(row["coordinate_precision_decimals"]) is not None and number(row["coordinate_precision_decimals"]) <= 2
            ),
        },
        "duplicates": {
            "colocated_groups": len(group_rows),
            "records_in_colocated_groups": sum(len(members) for members in group_rows.values()),
            "primary_records": sum(row["is_primary_record"] == "Y" for row in rows),
            "group_size_mismatches": len(group_size_mismatches),
            "primary_selection_mismatches": len(primary_mismatches),
        },
        "numeric_range_checks": numeric_checks,
        "relationship_checks": relationship,
        "selected_field_coverage": coverage,
        "known_interpretation_limits": [
            "Mapped terrain, climate, soil and geology values are spatial overlays, not direct spring measurements.",
            "The 30 m DEM drainage area is a surface catchment proxy, not a hydrogeological recharge area.",
            "The 299-point WATSAN dataset is not validated ground truth and its recharge-area fields must not be used as model targets or predictors without a leakage audit.",
            "Fault, fold and lineament distances are structural context, not proof of a hydraulic connection.",
            "Duplicate groups are proximity candidates and require human confirmation before records are merged or removed.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()

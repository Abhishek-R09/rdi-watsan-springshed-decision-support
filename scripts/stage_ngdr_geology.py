"""Stage NGDR Uttarakhand fault and lithology GeoJSON feature attributes.

This is a format-preserving staging step. Geometry remains unchanged in the
immutable raw GeoJSON; staged rows retain an explicit GeoJSON feature locator.
No spring-to-geology spatial join is attempted here.
"""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "00_raw" / "ngdr_geology"
STAGED = ROOT / "data" / "01_staged" / "ngdr_geology"

SOURCES = [
    {
        "key": "faults",
        "source_id": "SRC-013",
        "dataset": "NGDR Uttarakhand Fault",
        "raw_path": RAW / "faults" / "FAULT_STATE_UTTARAKHAND.geojson",
        "output": STAGED / "faults" / "csv" / "ngdr_uttarakhand_fault_features_v1.csv",
        "quality_flag": "Verify: NGDR state-scale fault layer. Do not treat proximity as a mapped spring connection without site and hydrogeological confirmation.",
    },
    {
        "key": "lithology",
        "source_id": "SRC-014",
        "dataset": "NGDR Uttarakhand Lithology",
        "raw_path": RAW / "lithology" / "LITHOLOGY_STATE_UTTARAKHAND.geojson",
        "output": STAGED / "lithology" / "csv" / "ngdr_uttarakhand_lithology_features_v1.csv",
        "quality_flag": "Verify: NGDR state-scale lithology layer. Polygon assignment to a spring remains an inferred map overlay requiring field confirmation, especially near contacts.",
    },
    {
        "key": "folds",
        "source_id": "SRC-015",
        "dataset": "NGDR Uttarakhand Fold",
        "raw_path": RAW / "folds" / "FOLD_STATE_UTTARAKHAND.geojson",
        "output": STAGED / "folds" / "csv" / "ngdr_uttarakhand_fold_features_v1.csv",
        "quality_flag": "Verify: NGDR state-scale fold layer. Do not treat fold proximity as a mapped spring connection without site and hydrogeological confirmation.",
    },
]


def text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def bounds(geometry):
    coordinates = geometry.get("coordinates") if geometry else None
    pairs = []

    def walk(value):
        if isinstance(value, (list, tuple)):
            if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
                pairs.append((value[0], value[1]))
            else:
                for child in value:
                    walk(child)

    walk(coordinates)
    if not pairs:
        return ""
    longitudes, latitudes = zip(*pairs)
    return f"{min(longitudes):.8f},{min(latitudes):.8f},{max(longitudes):.8f},{max(latitudes):.8f}"


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, quoting=csv.QUOTE_ALL, lineterminator="\n", restval="")
        writer.writeheader()
        writer.writerows(rows)


def stage_source(source):
    payload = json.loads(source["raw_path"].read_text(encoding="utf-8"))
    features = payload.get("features", [])
    property_columns = sorted({key for feature in features for key in (feature.get("properties") or {})})
    columns = [
        "source_id",
        "source_dataset",
        "source_feature_locator",
        "source_feature_id",
        "geometry_type",
        "geometry_bounds_wgs84",
        "staging_quality_flag",
        "source_notes",
    ] + property_columns
    rows = []
    for index, feature in enumerate(features, start=1):
        geometry = feature.get("geometry") or {}
        properties = feature.get("properties") or {}
        row = {
            "source_id": source["source_id"],
            "source_dataset": source["dataset"],
            "source_feature_locator": f"GeoJSON feature {index}",
            "source_feature_id": text(feature.get("id")),
            "geometry_type": text(geometry.get("type")),
            "geometry_bounds_wgs84": bounds(geometry),
            "staging_quality_flag": source["quality_flag"],
            "source_notes": "Original feature geometry is retained unchanged in the raw GeoJSON. No spatial join, simplification, correction, deduplication, or interpretation was applied.",
        }
        row.update({key: text(value) for key, value in properties.items()})
        rows.append(row)
    write_csv(source["output"], columns, rows)
    return {
        "key": source["key"],
        "source_id": source["source_id"],
        "dataset": source["dataset"],
        "raw_path": str(source["raw_path"].relative_to(ROOT)).replace("\\", "/"),
        "staged_csv": str(source["output"].relative_to(ROOT)).replace("\\", "/"),
        "feature_count": len(rows),
        "property_columns": property_columns,
        "geometry_types": sorted({row["geometry_type"] for row in rows}),
        "crs": payload.get("crs", {}),
    }


def main():
    metadata = {"sources": [stage_source(source) for source in SOURCES]}
    output = STAGED / "metadata" / "ngdr_uttarakhand_geology_v1_metadata.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

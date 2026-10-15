"""AG-ORC: execute only the dependency paths documented in agents/README.md."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import catchment, composer, lineage, specialists, spring, terrain, verifier, vulnerability
from .specs import ROOT, contracts
from .storage import RunStore, checksum


def assess(submission: dict, output_root: Path | None = None, vulnerability_session=None) -> tuple[RunStore, dict]:
    if not isinstance(submission, dict):
        raise ValueError("Assessment input must be a JSON object")
    mode = submission.get("mode", "catchment")
    if mode not in {"catchment", "springshed"}:
        raise ValueError("mode must be catchment or springshed")
    include_vulnerability = submission.get("include_vulnerability", False)
    if not isinstance(include_vulnerability, bool):
        raise ValueError("include_vulnerability must be true or false")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    store = RunStore(run_id, contracts(), output_root)
    input_file = store.directory / "submission.json"
    with input_file.open("xb") as stream:
        stream.write(json.dumps(submission, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
    valid_location, _, _ = spring.validated_location(submission.get("location"))
    store.emit("AG-ORC.run_context", "complete" if valid_location else "unavailable",
               "Submission preserved with a new run ID" if valid_location else "Submission preserved; geographic work blocked by invalid or CRS-ambiguous coordinates",
               payload={"mode": mode, "spring_id": submission.get("spring_id"),
                        "original_location": submission.get("location"),
                        "input_file": str(input_file.relative_to(ROOT)) if input_file.is_relative_to(ROOT) else str(input_file),
                        "input_sha256": checksum(input_file), "contract_versions": {key: value["version"] for key, value in store.contracts.items()}},
               upstream=["EXT-USER"], rule_ids=["R-ORC-01"])
    spring.run(store, submission)
    if include_vulnerability:
        vulnerability.run(store, submission, vulnerability_session)
    point = store.get("AG-SPR.location_evidence")["payload"].get("processing_point")
    snapshot, gaps = terrain.select_snapshot(point)
    store.emit("AG-ORC.source_selection", "complete" if snapshot else "unavailable",
               "Approved local snapshot selected" if snapshot else "No usable approved local snapshot",
               payload={"snapshot_id": snapshot.get("snapshot_id") if snapshot else None,
                        "selected_sources": [snapshot["dem"]["source_id"]] if snapshot else [],
                        "dem": snapshot.get("dem") if snapshot else None, "gaps": gaps},
               upstream=["AG-ORC.run_context", "AG-SPR.location_evidence"],
               source_refs=[{"source_id": snapshot["dem"]["source_id"],
                             "tiles": snapshot["dem"]["tiles"],
                             "transformation_ids": snapshot["dem"]["transformation_ids"]}] if snapshot else [],
               rule_ids=["R-ORC-02"], snapshot_id=snapshot.get("snapshot_id") if snapshot else None,
               issues=gaps)
    terrain.run(store, snapshot, gaps)
    catchment.run(store)
    if mode == "springshed":
        for agent_id in ["AG-GEO", "AG-RAI", "AG-LAS", "AG-SHD"]:
            specialists.run(store, agent_id)
    specialist_ids = [key for key in store.records if key.split(".", 1)[0] in
                      {"AG-SPR", "AG-VUL", "AG-TER", "AG-CAT", "AG-GEO", "AG-RAI", "AG-TMP", "AG-LAS", "AG-SHD"}]
    store.emit("AG-ORC.assessment_manifest", "complete", "Scheduled specialist results frozen before lineage and verification",
               payload={"specialist_output_ids": specialist_ids,
                        "output_statuses": {key: store.get(key)["status"] for key in specialist_ids},
                        "mode": mode,
                        "not_scheduled_agent_ids": [item for item in ["AG-VUL", "AG-GEO", "AG-RAI", "AG-TMP", "AG-LAS", "AG-SHD"]
                                                    if not any(key.startswith(item + ".") for key in specialist_ids)]},
               upstream=specialist_ids, rule_ids=["R-ORC-03"],
               snapshot_id=snapshot.get("snapshot_id") if snapshot else None)
    lineage.run(store)
    verifier.run(store)
    composer.run(store)
    status = store.get("AG-VER.release_status")["payload"]["AG-CAT.catchment_geometry"]
    store.emit("AG-ORC.dependency_status", "complete", "Required and optional handoffs recorded",
               payload={"catchment": status, "springshed": "unavailable" if mode == "springshed" else "not scheduled",
                        "vulnerability": store.get("AG-VUL.vulnerability_assessment")["status"] if include_vulnerability else "not scheduled",
                        "gaps": gaps}, upstream=["AG-LIN.lineage_issues", "AG-VER.release_status"],
               rule_ids=["R-ORC-03"])
    store.emit("AG-ORC.execution_record", "complete", "Versioned agent results saved in execution order",
               payload={"output_ids_in_order": list(store.records), "run_directory": str(store.directory)},
               upstream=["AG-ORC.dependency_status", "AG-COM.export_manifest"], rule_ids=["R-ORC-03"])
    return store, store.get("AG-COM.assessment_summary")

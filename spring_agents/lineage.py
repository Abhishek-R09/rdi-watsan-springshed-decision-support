"""AG-LIN: current contract map and per-run source-to-result trace."""

from __future__ import annotations

import csv
from collections import defaultdict

from .specs import ROOT
from .storage import RunStore


def _rows(relative: str) -> list[dict]:
    with (ROOT / relative).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def run(store: RunStore) -> None:
    contracts = store.contracts
    producers = defaultdict(list)
    for agent_id, spec in contracts.items():
        for output_id in spec["outputs"]:
            producers[output_id].append(agent_id)
    edges, issues = [], []
    for consumer_id, spec in contracts.items():
        for input_id in spec["inputs"]:
            owners = producers.get(input_id, [])
            edges.append({"from": input_id, "to": consumer_id, "producer": owners[0] if len(owners) == 1 else None,
                          "status": "declared" if len(owners) == 1 else "unresolved"})
            if len(owners) != 1:
                issues.append(f"R-LIN-01: {consumer_id} input {input_id} has {len(owners)} declared producers")
    store.emit("AG-LIN.contract_map", "provisional" if issues else "complete",
               "Agent input/output IDs matched against current specifications",
               payload={"agents": contracts, "edges": edges}, rule_ids=["R-LIN-01"], issues=issues)
    source_rows = {row["source_id"]: row for row in _rows("docs/source-register/source-register.csv")}
    raw_rows = _rows("docs/source-register/raw-intake-manifest.csv")
    transform_rows = _rows("docs/source-register/transformation-log.csv")
    manifest = store.get("AG-ORC.assessment_manifest")
    targets = manifest["payload"].get("specialist_output_ids", []) if manifest else []
    visited, nodes, links = set(), [], []

    def visit(output_id: str, active: set[str]) -> None:
        if output_id in active:
            issues.append(f"R-LIN-04: cyclic upstream path at {output_id}")
            return
        if output_id in visited:
            return
        record = store.get(output_id)
        if record is None:
            issues.append(f"R-LIN-02: missing recorded output {output_id}")
            return
        active.add(output_id)
        for parent in record["upstream_output_ids"]:
            links.append({"from": parent, "to": output_id})
            if parent != "EXT-USER":
                visit(parent, active)
        active.remove(output_id)
        visited.add(output_id)
        nodes.append({"output_id": output_id, "agent_id": record["agent_id"],
                      "status": record["status"], "reason": record["reason"],
                      "created_at_utc": record["created_at_utc"], "units": record["units"], "crs": record["crs"],
                      "record_sha256": record["record_sha256"],
                      "rule_ids": record["rule_ids"], "source_refs": record["source_refs"],
                      "snapshot_id": record["snapshot_id"],
                      "spec_version": record["spec_version"],
                      "field_input": {"input_file": record["payload"].get("input_file"),
                                      "input_sha256": record["payload"].get("input_sha256")}
                      if output_id == "AG-ORC.run_context" else None})

    for target in targets:
        visit(target, set())
    sources = []
    for node in nodes:
        for ref in node["source_refs"]:
            source_id = ref.get("source_id")
            if not source_id:
                issues.append(f"R-LIN-03: source reference without ID in {node['output_id']}")
                continue
            if source_id not in source_rows:
                issues.append(f"R-LIN-03: unregistered {source_id} in {node['output_id']}")
            raw = [row for row in raw_rows if row["source_id"] == source_id]
            claimed_ids = ref.get("transformation_ids")
            if not isinstance(claimed_ids, list):
                issues.append(f"R-LIN-03: applied transformation IDs not recorded for {source_id} in {node['output_id']}")
                claimed_ids = []
            transforms = [row for row in transform_rows if row["transformation_id"] in claimed_ids
                          and row["input_source_id"] == source_id]
            missing_transforms = set(claimed_ids) - {row["transformation_id"] for row in transforms}
            if missing_transforms:
                issues.append(f"R-LIN-03: unresolved transformations for {source_id}: {sorted(missing_transforms)}")
            if not raw:
                issues.append(f"R-LIN-03: no raw intake record for {source_id}")
            sources.append({"source_id": source_id, "used_by": node["output_id"],
                            "register_row": source_rows.get(source_id), "raw_intake": raw,
                            "transformations": transforms})
    snapshot_id = (store.get("AG-ORC.source_selection") or {}).get("payload", {}).get("snapshot_id")
    store.emit("AG-LIN.run_trace", "provisional" if issues else "complete",
               "Recorded ancestry for scheduled specialist outputs",
               payload={"targets": targets, "not_scheduled_agent_ids": manifest["payload"].get("not_scheduled_agent_ids", []) if manifest else [],
                        "nodes": nodes, "links": links, "sources": sources,
                        "source_register": "docs/source-register/source-register.csv",
                        "raw_manifest": "docs/source-register/raw-intake-manifest.csv",
                        "transformation_log": "docs/source-register/transformation-log.csv"},
               upstream=["AG-ORC.assessment_manifest"], rule_ids=["R-LIN-02", "R-LIN-03", "R-LIN-04"],
               snapshot_id=snapshot_id, issues=issues)
    store.emit("AG-LIN.lineage_issues", "provisional" if issues else "complete",
               "Broken and ambiguous lineage links listed", payload={"issues": issues},
               upstream=["AG-LIN.contract_map", "AG-LIN.run_trace"],
               rule_ids=["R-LIN-01", "R-LIN-02", "R-LIN-03", "R-LIN-04"], issues=issues)

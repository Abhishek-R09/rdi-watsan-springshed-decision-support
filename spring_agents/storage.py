"""Append-only per-run assessment records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import result
from .specs import ROOT, validate_output


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RunStore:
    def __init__(self, run_id: str, contracts: dict[str, dict], output_root: Path | None = None):
        self.run_id = run_id
        self.contracts = contracts
        self.directory = (output_root or ROOT / "data/03_outputs/assessments") / run_id
        self.records: dict[str, dict] = {}
        self.directory.mkdir(parents=True, exist_ok=False)

    def write(self, record: dict) -> dict:
        output_id = record["output_id"]
        validate_output(output_id, self.contracts)
        if record["run_id"] != self.run_id or output_id in self.records:
            raise ValueError(f"Duplicate or wrong-run output: {output_id}")
        record["record_sha256"] = hashlib.sha256(canonical_json(record)).hexdigest()
        path = self.directory / record["agent_id"] / f"{output_id.split('.', 1)[1]}.json"
        path.parent.mkdir(exist_ok=True)
        with path.open("xb") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False).encode("utf-8"))
        self.records[output_id] = record
        return record

    def emit(self, output_id: str, status: str, reason: str, **kwargs) -> dict:
        spec = self.contracts[output_id.split(".", 1)[0]]
        return self.write(result(output_id, self.run_id, status, reason, spec_version=spec["version"], **kwargs))

    def get(self, output_id: str) -> dict | None:
        return self.records.get(output_id)

"""Shared machine envelope for the IDs defined in agents/README.md."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


STATUSES = {"complete", "provisional", "unavailable", "failed"}


def result(
    output_id: str,
    run_id: str,
    status: str,
    reason: str,
    *,
    payload: dict[str, Any] | None = None,
    upstream: list[str] | None = None,
    source_refs: list[dict[str, Any]] | None = None,
    rule_ids: list[str] | None = None,
    spec_version: str | None = None,
    snapshot_id: str | None = None,
    units: str | None = None,
    crs: str | None = None,
    issues: list[str] | None = None,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"Invalid status: {status}")
    agent_id = output_id.split(".", 1)[0]
    if not output_id.startswith("AG-") or "." not in output_id:
        raise ValueError(f"Invalid output ID: {output_id}")
    return {
        "output_id": output_id,
        "run_id": run_id,
        "agent_id": agent_id,
        "spec_version": spec_version,
        "status": status,
        "reason": reason,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": snapshot_id,
        "units": units,
        "crs": crs,
        "upstream_output_ids": list(upstream or []),
        "source_refs": list(source_refs or []),
        "rule_ids": list(rule_ids or []),
        "payload": payload or {},
        "issues": list(issues or []),
    }

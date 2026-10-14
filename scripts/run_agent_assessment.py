"""Execute the documented agent graph against one submitted spring JSON form."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spring_agents.orchestrator import assess  # noqa: E402
from spring_agents.specs import contracts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="JSON file with location, field_form and mode")
    parser.add_argument("--check-contracts", action="store_true", help="Check declared agent input/output IDs only")
    args = parser.parse_args()
    if args.check_contracts:
        specs = contracts()
        producer = {item for spec in specs.values() for item in spec["outputs"]}
        missing = sorted({item for spec in specs.values() for item in spec["inputs"] if item not in producer})
        print(json.dumps({"agent_count": len(specs), "unresolved_input_ids": missing}, indent=2))
        return 1 if missing else 0
    if not args.input:
        parser.error("--input is required unless --check-contracts is used")
    try:
        submission = json.loads(args.input.read_text(encoding="utf-8"))
        store, summary = assess(submission)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Assessment could not start: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"run_id": store.run_id, "output_directory": str(store.directory),
                      "status": summary["status"], "reason": summary["reason"],
                      "summary_file": str(store.directory / "AG-COM/assessment_summary.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read the current agent contracts; avoid a competing hard-coded rulebook."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agents"
AGENT_FILES = {
    "AG-ORC": "orchestrator.md",
    "AG-SPR": "spring.md",
    "AG-TER": "terrain.md",
    "AG-CAT": "catchment.md",
    "AG-GEO": "geology.md",
    "AG-RAI": "rainfall.md",
    "AG-TMP": "temperature.md",
    "AG-LAS": "land_soil.md",
    "AG-SHD": "springshed.md",
    "AG-VUL": "vulnerability.md",
    "AG-LIN": "data_lineage.md",
    "AG-VER": "verifier.md",
    "AG-COM": "assessment_composer.md",
}


def contracts() -> dict[str, dict]:
    found = {}
    for agent_id, name in AGENT_FILES.items():
        text = (AGENT_DIR / name).read_text(encoding="utf-8")
        assert f"Agent ID: `{agent_id}`" in text, name
        version = re.search(r"^Version: ([0-9.]+)", text, re.M)
        output_section = text.split("## 3. WHAT YOU PRODUCE", 1)[1].split("## 4.", 1)[0]
        outputs = re.findall(r"^\| `(AG-[A-Z]{3}\.[a-z_]+)` \|", output_section, re.M)
        rule_section = text.split("## 4. YOUR DECISION RULES", 1)[1].split("## 5.", 1)[0]
        rules = re.findall(r"^\| `(R-[A-Z]{3}-[0-9]+)` \|", rule_section, re.M)
        input_line = re.search(r"^\| Input \| (.+) \|$", text, re.M)
        inputs = re.findall(r"AG-[A-Z]{3}\.[a-z_]+", input_line.group(1)) if input_line else []
        found[agent_id] = {
            "spec_path": f"agents/{name}",
            "version": version.group(1) if version else None,
            "outputs": outputs,
            "inputs": sorted(set(inputs)),
            "rules": rules,
        }
    return found


def validate_output(output_id: str, all_contracts: dict[str, dict]) -> None:
    producer = output_id.split(".", 1)[0]
    if output_id not in all_contracts[producer]["outputs"]:
        raise ValueError(f"Output not declared in {producer}: {output_id}")

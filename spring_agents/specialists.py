"""Connected later-stage roles; their §4 rules contain no executable method yet."""

from __future__ import annotations

from .storage import RunStore


UPSTREAM = {
    "AG-GEO": ["AG-SPR.spring_profile", "AG-SPR.location_evidence", "AG-ORC.source_selection"],
    "AG-RAI": ["AG-SPR.location_evidence", "AG-ORC.source_selection"],
    "AG-TMP": ["AG-SPR.location_evidence", "AG-ORC.source_selection"],
    "AG-LAS": ["AG-SPR.location_evidence", "AG-ORC.source_selection"],
    "AG-SHD": ["AG-SPR.spring_profile", "AG-GEO.geological_evidence",
               "AG-CAT.catchment_geometry", "AG-RAI.rainfall_coverage", "AG-LAS.spatial_summaries"],
}


def run(store: RunStore, agent_id: str) -> None:
    if agent_id not in UPSTREAM:
        raise ValueError(agent_id)
    for output_id in store.contracts[agent_id]["outputs"]:
        store.emit(output_id, "unavailable",
                   f"{agent_id} has no reviewed executable source-specific rule or approved inputs for this output",
                   upstream=UPSTREAM[agent_id],
                   payload={"rule_review": "pending", "hydrogeological_validation": "not assessed"})

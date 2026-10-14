# AGENT: <name>

Status: Draft scaffold | Version: <version> | Date: <date>
Owner: <owner> | Domain reviewer: TBD | WATSAN review: not recorded

Agent ID: `AG-<UNIQUE>`. Copy to the agents folder and link [shared contracts and ID registry](../README.md) using the correct relative path. Register the ID in the index and define every output ID in this file before another agent cites it.

## SIPOC

| Element | Definition |
|---|---|
| Supplier | <exact AG-ID.output_id, SRC-ID and external actor IDs> |
| Input | <exact upstream output IDs, source IDs, fields, units and locators> |
| Process | <ordered domain work> |
| Output | <AG-ID.output_id for every output> |
| Customer | <each receiving AG-ID or EXT-ID and exact output ID> |

## 1. WHO YOU ARE

<Expert field, purpose, responsibility and limits of authority.>

## 2. WHAT YOU RECEIVE

<Exact upstream AG-ID.output_id and SRC-ID, required/optional fields, types, units, CRS, locator and upstream-status handling.>

## 3. WHAT YOU PRODUCE

| Output ID | Meaning / consumer |
|---|---|
| `AG-<UNIQUE>.<output_id>` | <what it contains and exact receiving agent ID> |

<Evidence labels, proposed paths and unresolved schema choices.>

## 4. YOUR DECISION RULES

| Rule ID | Purpose / condition | Exact SRC-ID and page/feature locator; or explicit exploratory gap | Applicability / units | Missing evidence | Version / review basis |
|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD |

Unresolved numerical settings are disabled, not executable defaults.

## 5. WHAT YOU MUST NOT DO

<Forbidden assumptions, protected data and neighbouring agents' responsibilities.>

## 6. REVIEWED LESSONS - judgment layer

None approved. Candidate lessons do not change decisions.

Approved entry: Premise -> Test -> Evidence -> Conclusion -> Decision; reviewer/date; applicability; affected version; review basis; rollback/supersession.

## 7. WHEN YOU FAIL OR ARE UNCERTAIN

<complete/provisional/unavailable/failed rules; conflicts; permitted fallback; next check.>

## 8. TOOLS AND PERMISSIONS

<Named assessment tools and local snapshot sources; refresh-only adapters if relevant; read/write/execute paths.>

## 9. STATE AND MEMORY NEEDS

<Run history; pinned snapshot identity; candidate/approved lesson separation; versioned reruns.>

## 10. EVIDENCE REVIEW AND CHECKS

<Literature and expert review of the method, assumptions and applicability; exact SRC-ID and locator. Field comparison when a suitable independently supported case exists. Mechanical checks only where expected results can be established independently.>

Without independently verified recharge boundaries, record hydrogeological validation as not assessed. Do not assign an automated polygon accuracy threshold or treat an output as its own reference.

## SOURCE REFERENCES

<List each DOC-ID and SRC-ID with exact file/link, page/row/feature locator or a clearly stated locator gap and availability status.>

## OPEN SPECIFICATION ITEMS

<Outstanding contracts, rules, source locators, adapters, field checks and reviewers.>

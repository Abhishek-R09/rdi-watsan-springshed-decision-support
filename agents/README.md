# Agent specifications: catchment and springshed system

Status: **Draft agent specifications; partial connected runtime in [`spring_agents/`](../spring_agents/README.md). No approved polygon method.**
Version: 0.2 | Date: 14 October 2026 | Owners: Abhishek Ramasubramanian and Rajat Panda.

Each agent owns its decision rules in **§4 of its own specification**. The catchment-stage operational drafts are in [Orchestrator](orchestrator.md), [Spring](spring.md), [Terrain](terrain.md), [Catchment](catchment.md), [Verifier](verifier.md) and [Assessment Composer](assessment_composer.md). These proposed rules require domain and implementation review before execution; the remaining specialist agents retain their own draft §4 sections for later work.

## Scope and authority

The agreed specialist decomposition expands the earlier Geospatial Evidence and Recharge Delineation roles. Catchment delineation is the first capability; springshed delineation follows it. **Direct Injection is parked in this agent scaffold**: it has no active specification, dependency or result here. Vulnerability joins as the [Vulnerability Agent](vulnerability.md) (`AG-VUL`), which runs Module A ([`scripts/module_a_vulnerability.py`](../scripts/module_a_vulnerability.py)) unchanged when a request asks for it. Their broader project goals remain in the baseline.

The [workspace AGENTS.md](../../AGENTS.md) and current user instructions govern these specifications. The [14 October application plan](../docs/Project1_Agent_System_Implementation_Plan.md) supplies evidence and architecture safeguards; its earlier grouping is context for this more detailed decomposition. The plan records the separate periodic data-refresh and local assessment workflows; the workspace AGENTS.md baseline has not been edited.

The existing plan specifies local Python rule-based agents without runtime LLM API calls. These files define the responsibilities and evidence limits of the thirteen named roles below; the accompanying Python package implements only the resolved portions of those contracts. At runtime, the user's coordinates select covering data from the approved local snapshot. TBD refresh adapters, schemas, methods and thresholds remain unresolved.

## Agent specifications

| Agent ID | Specification | Responsibility | Catchment-first stage |
|---|---|---|---|
| AG-ORC | [orchestrator.md](orchestrator.md) | Task coordination and execution record | Required |
| AG-SPR | [spring.md](spring.md) | Identity, location and field evidence | Required |
| AG-TER | [terrain.md](terrain.md) | Checked terrain evidence | Required |
| AG-CAT | [catchment.md](catchment.md) | Automatic surface-drainage boundary | Required |
| AG-GEO | [geology.md](geology.md) | Groundwater pathways and geological constraints | Later springshed stage |
| AG-RAI | [rainfall.md](rainfall.md) | Rainfall evidence and summaries | Later where applicable |
| AG-TMP | [temperature.md](temperature.md) | Relevant temperature context | Optional; not a catchment prerequisite |
| AG-LAS | [land_soil.md](land_soil.md) | Land/soil conditions and infiltration context | Later where applicable |
| AG-SHD | [springshed.md](springshed.md) | Integrate evidence into provisional recharge candidates | Later springshed stage |
| AG-VUL | [vulnerability.md](vulnerability.md) | Module A spring vulnerability score with its reasons | When the request sets `include_vulnerability` |
| AG-LIN | [data_lineage.md](data_lineage.md) | Map agent handoffs and trace each assessment to recorded inputs | Required |
| AG-VER | [verifier.md](verifier.md) | Independent checks and findings | Required |
| AG-COM | [assessment_composer.md](assessment_composer.md) | Explain, map and export released results | Required |

Each `AG-...` ID is defined again in its own file. A handoff ID has the form `AG-...<dot>output_name` and must appear in the producing agent's output table. Supplier and customer cells name these exact IDs. External actors are `EXT-USER` (field user supplying inputs and receiving results) and `EXT-WATSAN` (staff supplying or reviewing evidence); neither is an agent or an automatic source of approved rules. `STORE-HISTORY` denotes the versioned assessment history, not an agent. `REG-SRC` denotes the [source register](../docs/source-register/source-register.csv), keyed by `source_id`; `SRC-...` IDs resolve there. `REG-RAW` denotes the [raw-intake manifest](../docs/source-register/raw-intake-manifest.csv), identified by `source_id` and `relative_path`. `REG-TRN` denotes the [transformation log](../docs/source-register/transformation-log.csv), keyed by `transformation_id`. An unregistered source cannot silently become an input.

Document IDs used in these specifications are `DOC-BASE` = [workspace AGENTS.md](../../AGENTS.md), `DOC-IMPL` = [application implementation plan](../docs/Project1_Agent_System_Implementation_Plan.md), and `DOC-LIT` = [literature enrichment notes](../docs/literature-enrichment-notes.md). `REF-SB` = SindhuBank's [CLAUDE.md](../../../../Term%204/AAI/SindhuBank/CLAUDE.md) and its agent files, used only as a formatting reference. These document IDs identify guidance, not spring observations. Each geological or delineation claim still needs a source-register ID and a page, row or feature locator.

Each role is responsible for evidence selection, method applicability, interpretation and uncertainty within its stated discipline. A role does not supply professional credentials, certify field truth or allow unsupported assumptions.

## Dependency map

Catchment mode:

`AG-ORC.run_context -> AG-SPR.location_evidence -> AG-TER.terrain_package -> AG-CAT.catchment_geometry -> AG-ORC.assessment_manifest -> AG-LIN.run_trace -> AG-VER.verification_report -> AG-COM.assessment_summary`

With `include_vulnerability: true`, either mode also runs:

`AG-SPR.location_evidence -> AG-VUL.vulnerability_assessment + AG-VUL.input_gaps -> AG-ORC.assessment_manifest -> ... -> AG-COM.assessment_summary`

The data path and the agent handoffs are related but distinct:

| Stage | Record or handoff | What it shows |
|---|---|---|
| Periodic preparation | `REG-SRC` -> unchanged raw file recorded in `REG-RAW` -> conversion recorded in `REG-TRN` -> approved local snapshot | Which dated source product and reproducible conversion supplied a local layer. A register entry alone does not prove the file exists. |
| Request | `EXT-USER` -> `AG-ORC.run_context` + `AG-ORC.source_selection` | Which spring, coordinates, run, rules and approved snapshot were selected. |
| Analysis | `AG-SPR.location_evidence` -> `AG-TER.terrain_package` -> `AG-CAT.catchment_geometry` | Which named outputs produced the surface catchment. Optional/later specialists appear only when scheduled. |
| Trace | `AG-ORC.assessment_manifest` + recorded agent outputs + `REG-SRC`/`REG-RAW`/`REG-TRN` -> `AG-LIN.run_trace` + `AG-LIN.lineage_issues` | The actual source-to-result path and any missing or conflicting link for this run. `AG-LIN.contract_map` separately shows the specified handoffs. |
| Review and presentation | `AG-LIN.run_trace` -> `AG-VER.verification_report` -> `AG-COM.assessment_summary` | Independent checks followed by the user-facing result and provenance explanation. |

The Orchestrator coordinates the entire run; the sequence names dependencies, not steps the field user operates. Spring location checks and local layer selection must not require the user to assemble GIS layers or draw the initial polygon.

Springshed mode combines the terrain/catchment foundation with Geology, Rainfall and Land and Soil evidence. Temperature participates only where a reviewed rule gives it a purpose. These packages feed Springshed, then Verifier and Assessment Composer. Each specialist receives the relevant Spring location evidence.

First-pass land/soil summaries use an explicitly named search area. Summaries over generated candidate polygons are an optional later enrichment pass; they cannot be prerequisites for generating that same polygon. Connection evidence and infiltration suitability remain separate.

The submitted spring point and any selected surface outlet remain separate, explained features. No universal outlet-snapping policy is approved here.

## Shared input context: draft

Every invocation should carry:

- Run ID, mode, timestamp, agent/specification version and frozen rulebook version.
- Spring identity and source-linked original/processing coordinates, CRS and available accuracy.
- Upstream package references, checksums, coverage and statuses.
- Requested analysis extent and applicable reviewed scenario parameters.
- Source IDs, file/page/row/feature locators, dates, units and evidence types.

## Prepared snapshots and periodic refreshes

`EXT-USER` supplies the coordinates and field form. `AG-ORC.source_selection` identifies registered `SRC-...` products covering that location in the approved active local snapshot. The user does not locate or upload map layers. Provider adapters in the [tool registry](tool_registry.md) run only in a separate, controlled refresh workflow, subject to confirmed access and reuse terms. No assessment agent may scrape a portal or assume access.

“Latest” means the latest approved local snapshot, not data observed today: a terrain release may be static while rainfall updates on a different schedule. Each snapshot records provider, `SRC` ID, product/release ID, observation period, publication/update time, retrieval time, original URL or catalogue item, spatial extent, CRS, resolution, licence and checksum. A major product or method change needs a new or revised source-register entry and review before promotion; a newer date alone does not make two products interchangeable.

During refresh, source files or exact response bodies enter immutable `data/00_raw/` with the required manifest and checksum before processing. A reviewed, versioned snapshot is then promoted for new assessments. Each run pins its snapshot ID and source versions; reruns retain the original inputs unless explicitly started as new assessments. Out-of-coverage data is marked unavailable with the missing source/extent named, never treated as zero or retrieved silently. The initial surface catchment can proceed when its required DEM covers the basin, independently of optional geology, rainfall or temperature layers. A Google Maps display service may mark the spring and overlay generated polygons during a live demo; it supplies no analytical layer.

Use structured objects and JSON handoffs when implemented. Markdown files are specifications, not production handoff formats. Exact types, required fields and schema versions remain TBD.

## Shared result envelope: draft

| Field | Meaning |
|---|---|
| run_id / agent_id / spec_version / rulebook_version | Execution and controlling contracts |
| status / reason | complete, provisional, unavailable or failed with an explanation |
| outputs | Logical packages, units, geometry CRS and checksums |
| evidence | Source references and Source / Inferred / Verify labels; retain measurement, observation, staff explanation and community recall distinctions |
| decisions | Applied rule IDs, input references, methods/settings, alternatives and rationale |
| issues | Missingness, conflict, no-data, truncation, applicability and service failure |
| next_checks | Smallest evidence or field checks needed |
| verification | Applicable checks, including not-tested; separate from field validation |

Complete computation does not mean a recharge boundary is true or field-verified. Mechanical checks never upgrade evidence status. One optional failure does not erase other valid results. Unsupported conclusions remain unavailable or provisional under reviewed rules.

GeoJSON export uses WGS84. Distance/area calculations use a declared metric projected CRS; the pilot plan proposes WGS84/UTM 44N subject to extent checks. Keep square metres internally and display hectares. Record source/target CRS, resolution, no-data handling and transformations.

## Shared services and ownership

These are shared capabilities to specify later, not extra operational agents created here:

- Source register and snapshots: immutable raw evidence, access terms, checksum, reproducible transformations and approved active versions.
- `TOOL-LINEAGE` records per-run output, tool and rule events; `AG-LIN` reads those records and the registers to produce `AG-LIN.contract_map`, `AG-LIN.run_trace` and `AG-LIN.lineage_issues`. Unspecified links stay flagged.
- Assessment history: versioned inputs, outputs, reviewer comments and subsequent observations.
- Candidate lessons: findings with no authority to change behaviour.
- Approved lessons/change review: identified reviewer, evidence, applicability, version, rollback and documented review basis; WATSAN endorsement is separately recorded.

The student team owns specification changes; domain reviewers remain TBD. Agents cannot approve their own behavioural changes. Derived outputs are proposed under `data/03_outputs/assessments/<run_id>/<agent_id>/`; exact filenames remain to be agreed.

## Template and design references

Use [templates/agent_spec_template.md](templates/agent_spec_template.md): SIPOC followed by the ten-section SindhuBank pattern (`REF-SB`). Inspected references were SindhuBank's `CLAUDE.md` and `agents/risk_analytics.md`, `scenario_generator.md`, `normalizer.md`, `lineage.md` and `uat.md` on 14 October 2026. Banking formulas, thresholds, binary data gates and overwrite policies are not copied.

Project guidance: `DOC-BASE`, `DOC-IMPL` and `DOC-LIT`. Source evidence: [source register](../docs/source-register/source-register.csv), with `SRC-...` ID and original page, row or map feature where possible. An inaccessible original, such as the `SRC-011` paper in this checkout, remains a registered reference with its availability limit stated. Existing area numbers in `SRC-003`, `SRC-008` and `SRC-011` have different methods and certainty; none is assumed to be a verified polygon boundary.

## Review standard while boundaries are unavailable

Literature review defines candidate mechanisms, where each applies and where it may fail. A proposed spatial rule needs its `SRC-...` ID, precise page/figure/table, assumptions, and the domain reviewer who accepted it. The rule remains exploratory until that review. RDI/WATSAN field observations and springshed walks can later challenge or refine it. A source's reported area can support a plausibility discussion, but area alone cannot verify the location of a polygon.

Check mechanical properties when there is an independent expectation: IDs, source lineage, units, coordinate transformations, geometry validity and reproducibility. Do not invent automated polygon accuracy tests or a pass threshold while independently delineated reference boundaries are absent. Record hydrogeological validation as **not assessed**, and keep expert disagreements and missing observations visible. The existing held-out spring records can be preserved without implying that they contain verified boundaries.

## Review before implementation

- Finalise input/output schemas and required/optional fields.
- Resolve source access/coverage, adapters and bounded method policies.
- Give each proposed rule an exact `SRC-...` ID and page/feature locator, or mark the rationale exploratory with its missing source.
- Assign domain reviewers; document literature applicability and planned field checks.
- Use mechanical checks only where an independent expectation and justified tolerance exist.

Preserve the existing Tehri/Atlas holdouts. Do not use held-out outcomes to tune rules and then claim independent validation. These records do not supply confirmed recharge polygons. Do not invent a default search extent, snapping radius, stream threshold, recharge weight or structural barrier to fill an unresolved specification.

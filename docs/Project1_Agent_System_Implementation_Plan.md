# Project 1: rule-based agent system and deliverables

Status: **Draft for review — implementation not started by this document**.

Date: 14 October 2026. Team: Abhishek Ramasubramanian and Rajat Panda.

Purpose: preserve the detailed plan discussed with the project team, using SindhuBank's agent-specification, evidence, verification and reviewed-memory principles. This document does not claim WATSAN approval. The workspace AGENTS.md remains the baseline authority.

Repository refresh note: saved after pulling main through commit `ee07609`. The updated repository includes revised duplicate handling and separate input/test datasets. Existing test design must be inspected and respected during implementation; an input/test split of spring records does not by itself supply verified recharge-boundary labels.

## 1. Goal and implementation approach

Build a local demonstration application that accepts spring coordinates and a short field form, then automatically produces:

1. A transparent vulnerability assessment.
2. A provisional recharge-zone polygon and area range.
3. A best-case Direct Injection recharge calculation.
4. An evidence summary, unresolved questions and monitoring recommendations.

**The agents will be Python modules implementing documented rules. No AI-model API will be called at runtime.** ChatGPT Work or Claude Code will assist with writing specifications, developing code and reviewing evidence. External data services may supply geographic inputs.

The first release will serve the student demonstration. It will also provide reproducible exports, a user manual and an Excel fallback suitable for WATSAN review.

Use a local Preact field interface and Python analysis modules. Periodic, separately managed refreshes prepare reviewed, versioned local geographic and historical datasets. On an assessment, user-supplied coordinates select covering data from the active local snapshot; no analytical provider fetch occurs per coordinate. Local GIS processing produces the initial polygon automatically. Each assessment pins its snapshot and source versions for reproducibility. All implementation files remain under Application/. The current interface is a standalone preview; the backend connection remains to be built.

**14 October 2026 data-access decision:** The earlier per-assessment acquisition proposal is superseded. Analytical inputs are stored locally and refreshed periodically, outside field-user requests; refresh cadence and source-specific coverage are to be set after review. “Latest” means the latest *approved local snapshot*, with the underlying observation period and publication/retrieval dates shown. A map service may be used during the live demo to display the spring and generated polygon. [Agent tool contracts](../agents/tool_registry.md) distinguish refresh tools from assessment tools.

## 2. Apply SindhuBank's design discipline

### Agent specifications before code

Every agent receives the same ten-section specification used in SindhuBank:

1. Role and purpose.
2. Exact inputs and their sources.
3. Exact outputs and downstream consumers.
4. Decision rules.
5. Prohibited actions.
6. Reviewed lessons from previous assessments.
7. Failure and uncertainty handling.
8. Tools and permissions.
9. State and memory needs.
10. Evidence review and applicable mechanical checks.

Add a SIPOC record — supplier, input, process, output and customer — for each agent.

Each rule must state its purpose, executable condition, units, evidence source, applicability and missing-data behaviour. Numerical thresholds must have a documented basis; unresolved thresholds stay disabled rather than acquiring invented defaults.

### Proposed operational agents

| Agent | Responsibility | Output |
|---|---|---|
| Intake and Data Quality | Validate coordinates, units, field records and evidence status; preserve conflicting readings. | Validated assessment input and issue list. |
| Geospatial Evidence | Retrieve local or remote layers, check coverage and prepare aligned spatial inputs. | Layer package, derived features and provenance manifest. |
| Recharge Delineation | Apply documented spring-specific rules and generate alternative candidate boundaries. | Candidate polygons, area range and rule explanations. |
| Vulnerability | Apply the Stressor-State-Impact-Response indicator score. | Indicator scores, drivers, completeness and applicable limitations. |
| DI Calculation | Calculate captured/injected water and conditional response bounds; evaluate safeguards. | Calculation table, assumptions, safety gaps and unavailable outputs. |
| Assessment Composer | Assemble the three modules into one readable result without introducing new facts. | Assessment summary, map, exports and next checks. |

"Agent" here denotes a module with a defined contract and permissions. The orchestrator executes the dependency graph; it does not make unrestricted autonomous decisions.

### Verification and development support

Use three support components rather than duplicating SindhuBank's entire committee:

- **Verifier/UAT:** independently checks calculations, geometry, input handling and claims.
- **Lineage:** records which inputs, versions, rules and tools produced each output.
- **Change Review:** checks proposed rule or contract changes for evidence, affected components, rollback and tests.

These are development and review controls. They do not become extra steps the field user must operate.

## 3. Data foundation, interfaces and execution

### Reconcile the current evidence record

Before building:

- Inventory the existing master table, original layers, field records and reference springsheds.
- Reconcile older acquisition entries with later download and processing records.
- Check that each pilot site has usable source layers, not merely values extracted at a spring point.
- Inventory any claimed reference boundaries with source, coordinate system, method and evidence status. At present no independently verified recharge polygons have been established for the pilot springs; distinguish reported areas, surface catchments and treatment areas from reference boundaries.
- Inspect the refreshed duplicate decisions and input/test split. Retain held-out sites and their exclusion buffers; do not use their outcomes to develop rules and then call the same exercise independent validation.

Keep existing raw files unchanged. Retain source values and locators through staging; review apparent duplicates rather than silently merging them.

### Shared contracts

Use structured objects internally and JSON for module handoffs. Human-readable reports are outputs, not the primary interface between modules.

Every assessment carries:

- Run ID, spring ID, location and input timestamp.
- Field values with units, source, date and evidence status.
- Input and layer versions/checksums.
- Rulebook version.
- Module results and module status.
- Warnings, missing evidence and execution history.

Each module returns one of **complete, provisional, unavailable or failed**, with a reason. One unavailable module must not erase valid outputs from another.

GeoJSON exports use WGS84 coordinates. Spatial calculations use WGS84 / UTM zone 44N for the Satpuli and Chamba pilots, with areas computed in square metres and displayed in hectares.

### Execution order

**Intake → data-quality checks → geospatial evidence → analysis modules → verification → composed result.**

Vulnerability and DI calculations can proceed without a completed recharge polygon where their inputs permit. Recharge-zone-dependent vulnerability indicators remain unavailable until a candidate zone exists. Avoid circular dependencies.

Every run gets its own output folder. Re-running an assessment creates a new version rather than overwriting the previous decision record.

### Data tools

Wrap existing processing scripts as reusable functions instead of rebuilding their functionality.

Before field use, acquire and stage covering terrain, geology, land/soil, and historical rainfall and temperature data where justified and available. Refresh these source collections periodically through a controlled maintenance workflow, rather than on each coordinate request. Retain the observation period, publication date, retrieval time, resolution, coverage and limitations of every source version. An approved active snapshot makes selected local versions available to assessments.

Refresh adapters must record source metadata, coverage, release identity and errors. New downloads enter immutable raw intake with checksums before reproducible staging and review. Promotion to the active snapshot is explicit; a new or incompatible product version is registered and reviewed first. Assessments query only that snapshot, record its ID and each source version, and report missing coordinate coverage as unavailable rather than silently fetching or inventing values. No credentials enter reports or version control.

A display basemap can mark the supplied spring and overlay generated catchment and candidate recharge polygons. The current interface uses OpenStreetMap tiles for its development preview; a Google Maps satellite/terrain basemap remains an option for the live demo. A basemap is visual context, not the analytical evidence used to establish a boundary; a local terrain view remains the offline display fallback.

## 4. Module behaviour

### A. Vulnerability

- Use the existing Stressor-State-Impact-Response framework, interpretable 1–3 indicator scoring and equal weights.
- Develop the indicator definitions and thresholds in a reviewable rulebook before implementation.
- Preserve distinctions between measured discharge, staff explanation and community recall.
- Show each indicator's contribution and the evidence supporting it.
- Do not silently renormalise an incomplete assessment into a comparable full score. Show available indicators and completeness; with missing required indicators, label the overall classification unavailable or provisional according to the frozen scoring specification.
- Introduce alternative weights only after recorded WATSAN review.
- Respect the refreshed data documentation's distinction between decline over time and seasonality alone: an always-seasonal spring is not automatically declining. Field evidence of change is needed for decline-related validation.

### B. Recharge-zone delineation

Build an automated spatial rule engine, with terrain used as an initial search guide and geology used to assess plausible connection.

The engine will:

1. Prepare terrain, geological and land-surface evidence around the outlet.
2. Apply applicable spring-type and structural rules.
3. Keep infiltration suitability separate from evidence of connection to the spring.
4. Generate spatially coherent candidate polygons.
5. Run documented alternative assumptions.
6. Report the resulting boundaries, areas and sensitivity.

Do not adopt universal ridge, fault or stream barriers. Do not infer rock dip from surface slope. Treat DEM-derived lineaments as unvalidated candidates.

Use discharge and rainfall for a conditional area plausibility check when their evidence supports it. Do not force a polygon to match an unverified recharge-area label or a single discharge measurement.

The spatial rulebook must fix search extent, layer scoring, weights, structural interpretation, thresholds and polygon-generation settings before reference testing. Where those choices lack evidence, use explicitly documented exploratory scenarios; their outputs remain preliminary.

An area range represents variation between scenarios, not a statistical confidence interval. Missing geological evidence can yield a terrain-based investigation zone, clearly distinguished from a supported recharge-zone estimate.

### C. Direct Injection

Implement deterministic, unit-checked water-balance calculations:

- Captured/injected volume from connected roof area, rainfall and documented efficiencies.
- Maximum equivalent additional flow under an explicit assumed delivery period and spring-connection scenario.
- Conditional water-level calculation only when area of influence and specific yield are supplied as sourced values or labelled scenarios.

Keep injected volume, groundwater response and possible spring-flow response separate. Do not introduce an assumed aquifer connection as a fact.

Missing first-flush, filtration, overflow/clogging inspection or water-quality evidence must appear in the result. The system produces planning calculations, not installation approval.

## 5. Memory and controlled improvement

Maintain three stores, following SindhuBank:

| Store | Contents | Effect on decisions |
|---|---|---|
| Assessment history | Inputs, outputs, rule versions, reviewer comments and subsequent observations. | Traceability and retrieval of relevant past cases. |
| Candidate lessons | Disagreements, apparent patterns and proposed rule changes. | No automatic authority to change behaviour. |
| Approved lessons | Reviewed evidence, applicability, effective version and tests. | Changes the relevant module through a versioned rule release. |

Each candidate lesson follows **Premise → Test → Evidence → Conclusion → Decision**. For springs, tests must examine geological differences, measurement conditions and alternative explanations; bank cohort thresholds are not transferred.

New observations enter the evidence register first. Agent-generated polygons retain their estimated status and never become verified reference labels merely through storage.

A rule change requires an identified owner, supporting evidence, affected modules, rollback path and proving test. Student-team review can authorise experimental demo versions; WATSAN endorsement must be separately recorded and never implied.

Lessons may be narrowed, superseded or retracted. Preserve those histories.

## 6. Interface, exports and handover

The interface will provide:

- A spring-location and field-input form, with optional DI inputs.
- Data coverage and evidence-status indicators.
- A run-progress panel showing module status.
- Vulnerability results with drivers.
- A map distinguishing the outlet, terrain search area and alternative candidate zones.
- DI calculations with assumptions and safety gaps.
- An evidence/review panel and downloadable assessment package.

If remote basemap access fails, display the generated geometry over a local terrain view. Previously prepared pilot assessments must remain demonstrable without network access.

Deliver:

- Working application and reproducible pilot assessments.
- CSV/XLSX assessment tables and GeoJSON maps.
- Vulnerability and DI Excel fallback using the same documented calculations.
- Rulebook, agent specifications, lineage and validation report.
- Field form, user manual and monitoring handover.
- Presentation evidence and technical appendices for student-authored academic work.

## 7. Testing, review and acceptance

### Functional verification

Test valid inputs, missing coordinates, reversed coordinates, unsupported locations, no-data coverage, service failure, conflicting observations, absent discharge, missing geology and incomplete DI records.

Independently check:

- Score arithmetic and boundary conditions.
- Rainfall and discharge unit conversions.
- Roof-area and efficiency sensitivity.
- Polygon validity, coordinate transformations and area calculations.
- No-data handling and separation of source values from derived values.
- Reproduction of a saved run from its inputs and rule version.

Compare Excel outputs with Python calculations using a stated numerical tolerance.

### Evidence-based validation

- Use independently supported reference springsheds as case-level checks only if such boundaries become available.
- Record reference method and uncertainty before calculating overlap or area difference; reported area alone cannot verify polygon placement.
- Where feasible, reserve one site from rule development and freeze rules before assessing it, respecting the repository's existing holdout split.
- Where a suitable boundary exists, report its overlap, area difference, expert disagreement and sensitivity. Otherwise record hydrogeological validation as not assessed; do not claim regional accuracy from a small or unverified set.
- Freeze vulnerability results before expert ranking review and retain disagreements.
- DI verification establishes arithmetic and assumptions, not observed impact.

### Acceptance conditions

The demo passes when all three modules operate end-to-end on documented pilot inputs; supported polygons are generated without manual drawing; unavailable outputs have explicit reasons; every substantive result has traceable evidence or a labelled assumption; exports reproduce the screen results; and saved assessments rerun consistently.

## 8. Delivery sequence and assumptions

| Period | Work and review output |
|---|---|
| 14–20 October | Reconcile sources; register pilot/reference sites; draft agent contracts and rulebooks; gather field evidence and WATSAN feedback. |
| 21–24 October | Build shared contracts, intake, lineage, vulnerability and DI modules; verify calculations and workbook fallback. |
| 25–28 October | Implement recharge scenarios, automated polygons and case-level validation. |
| 29 October–1 November | Integrate interface, exports, review records and controlled memory workflow. |
| 2–4 November | Complete reproducibility checks, manuals, monitoring handover and limitations report. |
| 5–6 November | Demonstrate to RDI/WATSAN, record feedback and deliver the reviewed release. |

Defaults: local Python modules; no runtime LLM API; Preact field interface (currently a standalone preview); periodic reviewed data refreshes and a pinned local snapshot per assessment; a configurable display basemap for the live demo; no supervised boundary model trained on a few unverified examples; no automatic rule promotion; and no expansion into the other DoCC projects.

Exact hydrological thresholds are outputs of the documented rule-development and review stage, not assumptions fabricated by the implementer. Until frozen, affected outputs remain exploratory.

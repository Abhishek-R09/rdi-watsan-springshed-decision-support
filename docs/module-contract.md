# How the modules fit together (draft v3, 2026-10-15)

The tool has three modules:

- **Module A:** vulnerability score. `assess()` in `scripts/module_a_vulnerability.py`.
- **Module B:** springshed and recharge zone. `delineate()` in `scripts/module_b_springshed.py`.
- **Module C:** DI impact. `estimate()` in `scripts/module_c_di_impact.py`.

Since 15 October 2026, the three run together in the spring tool. `scripts/spring_tool_server.py` runs A, then B, then C, and serves the map page in `app/`. The page and the server share the request and reply shapes in `app/src/api.ts`. How to use the tool and how each module works: [spring-tool-guide.md](spring-tool-guide.md). The agent runtime and the page in `interface/` described below are a separate, earlier route.

The intended whole tool runs locally and calls no paid AI service. A small rule-based orchestrator is proposed to check inputs and coordinate the modules. The agent runtime in [`spring_agents/`](../spring_agents/README.md) is that orchestrator. Module A joins it as the Vulnerability Agent ([`agents/vulnerability.md`](../agents/vulnerability.md)), and the Preact page in [`interface/`](../interface/README.md) reaches it through the local server `scripts/serve_tool.py`. Module A's map layers come from an approved, versioned map set made with `scripts/module_a_snapshot.py` (rule `R-VUL-03`).

The fuller design is in [`Project1_Agent_System_Implementation_Plan.md`](Project1_Agent_System_Implementation_Plan.md). That plan covers the agent specifications, lineage, memory and testing. This note covers only what each module takes in and gives back, so that the modules join without rework.

## 1. Every module takes the same input

```json
{
  "spring": {
    "name": "Nauli Dhara",
    "latitude": 29.91903,
    "longitude": 78.55647,
    "elevation_m": 1481
  },
  "field": {
    "flow_vs_past": "a_bit_less",
    "lean_flow_lpm": 2.5,
    "households": 35
  },
  "from_modules": {
    "B": { "...": "Module B's output, when it has run" }
  }
}
```

- **`spring`** is required. Latitude and longitude are in decimal degrees (WGS84), and elevation is in metres.
- **`field`** is optional. It holds the answers from the Spring & DI field form. For Module A, the names and allowed values are in `OPTIONAL` in `scripts/module_a_vulnerability.py`. Each module ignores the answers it does not use.
- **`from_modules`** is optional. It holds the outputs of modules that have already run.

## 2. Every module returns the same shape

```json
{
  "module": "A",
  "title": "Spring vulnerability",
  "version": "v1 draft",
  "status": "complete | provisional | unavailable | failed",
  "spring": { "...": "the spring input, echoed back" },
  "result": { "...": "module-specific, see below" },
  "confidence": "Low | Medium | High",
  "validation": "One sentence: has this module been checked against field evidence yet?",
  "rationale": ["Plain sentences, each one backed by a value in result"],
  "missing_inputs": [{ "id": "flow_vs_past", "indicator": "...", "needs": "..." }],
  "warnings": ["For example: the map elevation is 300 m off the given elevation"],
  "report_markdown": "A one-page report for printing"
}
```

**`status`** uses the four words from the implementation plan:

- **complete:** the module had what it needs.
- **provisional:** a result exists but rests on missing or weak evidence. For Module A, this covers any score without the decline question or with less than 75% of the weight covered.
- **unavailable:** the module could not produce a result, and the reason is in `warnings`.
- **failed:** the module hit an error.

**`confidence`** says how complete the inputs were (the page shows it as "Evidence"). It does not say the answer is right. **`validation`** says that separately: until a module has been compared with field evidence (known declining springs, walked springsheds, monitored DI sites), it says "Not yet validated" and why.

If one module is unavailable, the other modules' results still stand.

| Module | What goes in `result` |
|---|---|
| A | `score` (0-100), `class` (Low / Medium / High), `kind` (vulnerability or exposure score), `coverage_pct`, `indicators` (each with its value, score and points) |
| B | `recharge_zone` (GeoJSON polygons in WGS84, one per scenario), `area_ha` range, `method`, rule explanations |
| C | Injected volume, then the best-case change in lean-season discharge, kept separate from any water-level estimate. Each comes with its assumptions. |

## 3. How the modules connect

- **B into A.** Module A measures disturbed land (built-up, cropland and bare land) in a 500 m circle around the spring. Once Module B gives a recharge zone, Module A should measure inside that zone instead. Until then, Module A adds a warning that the circle was used.
- **A and B into C.** Module C uses Module B's zone, to check whether the handpump lies inside it, and Module A's flow answers as the baseline.

## 4. How to add a module

1. Write a function `run(inputs: dict) -> dict` that follows sections 1 and 2. Module A's version is `assess()` in `scripts/module_a_vulnerability.py`.
2. Add it to the orchestrator's run order.

The web page only reads these outputs. Each module can be built and tested on its own.

## 5. How Module A is called today (15 October 2026)

The page sends the agent runtime's request. Module A's parts of it are:

```json
{
  "include_vulnerability": true,
  "location": { "latitude": 29.91903, "longitude": 78.55647, "crs": "EPSG:4326", "elevation_m": 1481 },
  "field_form": { "vulnerability_answers": { "flow_vs_past": "a_bit_less", "lean_flow_lpm": 2.5, "households": 35 } }
}
```

`spring_agents/vulnerability.py` turns this into section 1's input and calls `assess()` in `scripts/module_a_vulnerability.py`. Module A's full result (section 2) is stored unchanged as `AG-VUL.vulnerability_assessment`, and `AG-COM.assessment_summary` carries a copy under `vulnerability`. `elevation_m` may be left out: the map elevation is then used, with a warning.

# How the modules fit together (draft v2, 2026-10-14)

The tool has three modules, built separately and joined later:

- **Module A:** vulnerability score (Rajat).
- **Module B:** recharge zone (Rajat's colleague).
- **Module C:** DI impact.

The whole tool runs locally and calls no paid AI service. A small rule-based orchestrator sits on top. It checks the inputs, runs the modules in order, and puts their results on one local web page (React/JS, to be built later).

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

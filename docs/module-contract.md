# How the modules fit together (draft v1, 2026-10-14)

The tool has three modules, built separately and joined later:

- **Module A:** vulnerability score (Rajat).
- **Module B:** recharge zone (Rajat's colleague).
- **Module C:** DI impact.

One agent sits on top and talks with the user. Each module is a **tool** that the agent can call. The agent collects the inputs, calls the modules, and explains their results. The modules do the scoring and the maths. The agent never makes up a number.

For the modules to join without rework, each one follows the same contract.

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
- **`field`** is optional. It holds answers from the Spring & DI field form. The names and allowed values are listed in `OPTIONAL` in `scripts/module_a_vulnerability.py`. A module ignores any answer it does not use.
- **`from_modules`** is optional. It holds the outputs of modules that have already run, so that one module can build on another.

## 2. Every module returns the same shape

```json
{
  "module": "A",
  "title": "Spring vulnerability",
  "version": "v1 draft",
  "spring": { "...": "the spring input, echoed back" },
  "result": { "...": "module-specific, see below" },
  "confidence": "Low | Medium | High",
  "rationale": ["Plain sentences, each one backed by a value in result"],
  "missing_inputs": [{ "id": "flow_vs_past", "question": "...", "why_it_matters": "..." }],
  "warnings": ["For example: the map elevation is 300 m off the given elevation"],
  "report_markdown": "A one-page report for printing"
}
```

| Module | What goes in `result` |
|---|---|
| A | `score` (0-100), `class` (Low / Medium / High), `coverage_pct`, `indicators` (each with its value, score and points) |
| B | `recharge_zone` (a GeoJSON polygon), `area_ha`, `method`, and the checks against the 57 delineated areas |
| C | Change in lean-season discharge and water level, with a low and a high estimate |

## 3. How the modules connect

- **B into A.** Module A measures disturbed land (built-up, cropland and bare land) in a 500 m circle around the spring. Once Module B gives a recharge zone, Module A should measure inside that zone instead. When `from_modules.B.result.recharge_zone` is present, Module A will use it. Until then, it notes that the circle was used.
- **A and B into C.** Module C needs Module B's area and Module A's flow and usage answers.

## 4. How to plug a module into the agent

1. Write a function `run(inputs: dict) -> dict` that follows sections 1 and 2.
2. Wrap it as a tool in `scripts/spring_agent.py`, the same way `assess_vulnerability` wraps Module A.
3. Add one line to the agent's instructions saying when to call it.

Module B can be built and tested on its own. It only needs a `run()` function that follows this contract. Joining it to the agent is then a small change.

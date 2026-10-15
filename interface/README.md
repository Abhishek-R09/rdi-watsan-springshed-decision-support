# Spring field interface

This is the field-facing UI for Project 1. The page uses Preact, Vite and Leaflet; no frontend account, map key or analytical API is required. When the local server `scripts/serve_tool.py` is running, the page runs real assessments through the Python agent runtime: the vulnerability score (Module A) and the recharge-zone status. Without the server it falls back to the illustrative preview.

```powershell
cd interface
npm ci
npm run dev
```

Open the local URL printed by Vite. In a second terminal, start the Python side with `python scripts/serve_tool.py` from the repository root; Vite forwards the page's `/api` calls to it (port 8765).

For everyday use, build the page once (`npm run build`) and run only `python scripts/serve_tool.py`, then open http://127.0.0.1:8765. The server serves `dist/` and the API together. `npm run build` checks TypeScript and produces the static site in `dist/`. The interface is responsive down to a phone screen and supports map clicks, manual WGS84 coordinates and an optional browser geolocation request. Field observations can be entered, and **Download prepared request JSON** exports the payload that a later backend can accept. The preview does not write assessment data to the Python service.

The map uses OpenStreetMap's standard tile server for a **display-only development basemap**, with visible attribution. It requests only viewed tiles; there is no prefetch or offline tile download. It needs a network connection for the background, while coordinate entry still works when tiles fail. A production field deployment should choose and configure a suitable map provider and review its service terms; Google Maps integration, if selected, needs its own provider integration and credentials. Basemap imagery must never be used as the evidence that determines a catchment or springshed boundary.

## Backend handoff

The TypeScript request shape in [`src/types.ts`](src/types.ts) matches the Python input keys: `mode`, `spring_id`, `include_vulnerability`, `location` with `EPSG:4326` and optional `elevation_m`, and `field_form` readings, conditions and `vulnerability_answers`. The Module A questions are listed in [`src/vulnerabilityQuestions.ts`](src/vulnerabilityQuestions.ts); a test checks them against Module A. `runAssessment()` in [`src/App.tsx`](src/App.tsx) posts the request to `POST /api/assess` on `scripts/serve_tool.py`, which listens on 127.0.0.1 only and has no authentication; it is meant for one person's own computer.

The progress view accepts browser events named `spring-agent-progress`. Each event must contain `runId`, a declared `agentId`, `status` (`waiting`, `running`, `complete`, `unavailable`, `needs_review`, or `not_scheduled`), and `message`; `outputId` is optional. The frontend accepts an event only for its active run ID. The server currently answers once the whole run is finished, and the page then sends one event per agent from that answer; a future SSE or WebSocket adapter could stream them instead. Preview events carry `demo: true` and are labelled as illustrative. The UI does not invent a catchment polygon, recharge area or verification result.

The map component currently shows only a submitted spring point. When a backend emits a reviewed map-layer manifest, add a GeoJSON overlay with its status and source trace. Keep the original spring point and any selected surface outlet as separate features; label a surface catchment as provisional and distinct from groundwater recharge.

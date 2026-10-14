# Spring field interface

This is the field-facing UI for Project 1. It is separate from the Python agent runtime for now. The page uses Preact, Vite and Leaflet; no frontend account, map key or analytical API is required to run the preview.

```powershell
cd interface
npm ci
npm run dev
```

Open the local URL printed by Vite. `npm run build` checks TypeScript and produces the static site in `dist/`. The interface is responsive down to a phone screen and supports map clicks, manual WGS84 coordinates and an optional browser geolocation request. Field observations can be entered, and **Download prepared request JSON** exports the payload that a later backend can accept. The preview does not write assessment data to the Python service.

The map uses OpenStreetMap's standard tile server for a **display-only development basemap**, with visible attribution. It requests only viewed tiles; there is no prefetch or offline tile download. It needs a network connection for the background, while coordinate entry still works when tiles fail. A production field deployment should choose and configure a suitable map provider and review its service terms; Google Maps integration, if selected, needs its own provider integration and credentials. Basemap imagery must never be used as the evidence that determines a catchment or springshed boundary.

## Backend handoff

The TypeScript request shape in [`src/types.ts`](src/types.ts) matches the current Python input keys: `mode`, `spring_id`, `location` with `EPSG:4326`, and `field_form` readings and conditions. Replace `previewWorkflow()` in [`src/App.tsx`](src/App.tsx) with a call that starts `spring_agents.orchestrator.assess` through an HTTP endpoint. The endpoint and authentication policy are **not specified or implemented** in this UI.

The progress view accepts browser events named `spring-agent-progress`. Each event must contain `runId`, a declared `agentId`, `status` (`waiting`, `running`, `complete`, `unavailable`, `needs_review`, or `not_scheduled`), and `message`; `outputId` is optional. The frontend accepts an event only for its active run ID. A future SSE or WebSocket adapter can translate backend events into that contract. Current preview events carry `demo: true` and are labelled as illustrative. The UI does not invent a catchment polygon, recharge area or verification result.

The map component currently shows only a submitted spring point. When a backend emits a reviewed map-layer manifest, add a GeoJSON overlay with its status and source trace. Keep the original spring point and any selected surface outlet as separate features; label a surface catchment as provisional and distinct from groundwater recharge.

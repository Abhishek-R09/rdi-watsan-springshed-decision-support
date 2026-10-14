# Proposed assessment tools and periodic-refresh adapters

Status: **Contract proposal, not implemented.** Version: 0.2 | Date: 14 October 2026. This file is referenced by the agent specifications. `SRC-...` IDs resolve to the [source register](../docs/source-register/source-register.csv); `AG-...` IDs resolve to the [agent index](README.md). Refresh runs separately from coordinate assessments; tool IDs identify bounded capabilities, not permission to browse arbitrary sites.

## Assessment services

| Tool ID | Responsibility | Access boundary |
|---|---|---|
| `TOOL-SNAPSHOT` | Select the approved active snapshot; query indexed local layers and historical series by coordinate, coverage and version. | Read-only source data; report missing coverage rather than fetching. Pin snapshot ID and source versions to the run. |
| `TOOL-FIELD-INTAKE` | Preserve a newly submitted field form and coordinates with run identity. | User-supplied input only; retain original values and evidence status. |
| `TOOL-GIS-RASTER` | Read, mosaic, reproject and sample rasters with documented CRS and no-data handling. | Local snapshot layers only; derived outputs versioned by run. |
| `TOOL-GIS-FLOW` | Condition a DEM and compute routing, upstream cells and surface catchment geometry. | Checked terrain package and reviewed outlet/routing rules only. |
| `TOOL-GIS-VECTOR` | Spatial joins, overlays, geometry checks and area calculations. | Registered vector layers and named upstream polygons only. |
| `TOOL-TIMESERIES` | Read and summarise stored dated rainfall or temperature with units and completeness. | Snapshot series and explicit observation periods only. |
| `TOOL-RULEBOOK` | Read a pinned, reviewed spatial rule version and its `SRC` locators. | Read-only during a run; no agent can approve or alter its own rules. |
| `TOOL-LINEAGE` | Record exact `AG` outputs, snapshot ID, `SRC` releases, processing settings and checksums by run ID for `AG-LIN` to assemble into a trace. | Append/version assessment history; no silent replacement. This recording capability is not the `AG-LIN` agent. |
| `TOOL-MAP` | Display supplied spring coordinates and generated polygons on a Google Maps basemap in the proposed live demo. | Display only; map imagery cannot determine analytical boundaries. Use a local terrain view if unavailable. |
| `TOOL-EXPORT` | Produce labelled report, map and CSV/GeoJSON packages from verified outputs. | No new scientific inference; preserve source and uncertainty labels. |

## Separate refresh and promotion services

| Tool ID | Responsibility | Access boundary |
|---|---|---|
| `TOOL-CATALOG` | Inspect registered provider release metadata, coverage, period and licence at refresh time. | Registered `SRC` entries and approved provider routes only. |
| `TOOL-FETCH` | Obtain selected source tiles, features or historical time windows through registered adapters at refresh time. | Permitlisted provider URLs/credentials and planned extent. |
| `TOOL-INTAKE` | Store exact source downloads immutably under `data/00_raw/`, checksum them and update intake/transformation registers. | No overwrite of originals; preserve source release and retrieval metadata. |
| `TOOL-PROMOTE` | Review staged data, coverage, units and source compatibility, then declare a versioned active snapshot. | Explicit review; never auto-promote a new product or alter prior snapshots. |

Refresh cadence depends on source update frequency, coverage needs, cost and review capacity; it is not fixed yet. No remote analytical provider is called per coordinate request. A source missing from the active snapshot stays unavailable until a reviewed refresh supplies it.

## Source adapters for periodic refresh

| Adapter ID | Registered source | Refresh position |
|---|---|---|
| `ADP-SPRING-RECORDS` | `SRC-003`, `SRC-008`, `SRC-017` when collected | Stage and index project-controlled spring records. New field forms enter through `TOOL-FIELD-INTAKE`. |
| `ADP-DEM-COP` | `SRC-018` | Prepare covering Copernicus GLO-30 DEM tiles under the existing project source-register record; access and coverage require confirmation before refresh. |
| `ADP-DEM-CARTO` | `SRC-022` | Access route, licence and automated retrieval are unresolved; previously downloaded tiles may be used only with their age/version labelled. |
| `ADP-GEO-GSI` | `SRC-013`, `SRC-014`, `SRC-015` | Stage registered local GSI geology vectors. Further NGDR/Bhukosh access and reuse terms remain to be checked; a map image cannot replace analytic vectors. |
| `ADP-RAIN-CHIRPS` | `SRC-020` | Prepare a dated local historical series from the registered CHIRPS v2 route. Assess and register any distinct release separately before replacement. |
| `ADP-RAIN-IMD` | `SRC-023` | Existing files were downloaded manually; automated access route is unresolved. |
| `ADP-LAND-WORLDCOVER` | `SRC-019` | Stage covering ESA WorldCover 2021 v200 tiles under the existing project source-register record; retain the 2021 observation year. |
| `ADP-SOIL-HWSD` | `SRC-021` | Registered FAO/IIASA release retrieval; confirm current release metadata and coverage before use. |
| `ADP-SOIL-SOILGRIDS` | `SRC-024` | Existing files were downloaded manually; automated access and terms remain unresolved. Match any later intake to the registered release and units. |
| `ADP-TEMPERATURE` | No historical `SRC` selected; `SRC-017` only if temperature is measured in the field | Placeholder for a source the team may discuss and register later. No provider or access route is specified. |

The adapters are proposals, not evidence that each provider offers automated access. Provider credentials, quotas, download size and update cadence require review before implementation. The proposed Google Maps display API is the only runtime external service in this design; it cannot replace analytical source rasters or vectors.

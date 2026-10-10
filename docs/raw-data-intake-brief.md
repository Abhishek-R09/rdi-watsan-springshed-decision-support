# Raw-data intake brief — 10 October 2026

## What we have, unchanged

The supplied `Discharge_Spring_Data.xlsx` is an intake source, not an analysis-ready or ground-truth training set. Its `All_Parameter` sheet contains 299 records and 17 fields; each coordinate pair is unique. The workbook has separate tabs for extracted terrain, land-cover, rainfall and spring attributes, plus `Discharge_lpm` with weighted annual discharge and a normalised score.

The `HIM_Spring (1).qgz` file is intact, but its data dependencies are not. It references local CSVs for elevation, land use, NDVI, permeability, rainfall and slope; a KML spring layer; and Uttarakhand boundary shapefiles. These must be obtained as original files before attempting to reproduce or assess the earlier map workflow.

Raw-file identity checks are in `docs/source-register/raw-intake-manifest.csv`. The acquisition queue is in `docs/source-register/acquisition-queue.csv`.

## Early quality flags — not corrections

- `recharge_area_ha` mixes integers, decimal values and text ranges; `discharge_lpm` is mainly text ranges.
- `Porosity`, `Permeability`, spring type, rock type and seasonal class use inconsistent spellings/case and mixed terminology.
- The workbook's stated geographic coverage is not yet demonstrated as suitable for Chamba or Satpuli.
- The source and derivation of `Groundwater_Potential`, weighted discharge and normalised-score fields have not been documented. They remain unsuitable as modelling targets or predictors until lineage is audited.

These are flags for a transparent audit. No original raw values have been edited, harmonised or used for modelling.

## Collection order

1. Obtain the original WATSAN methodology, the missing QGIS dependencies and any historic monitoring data.
2. Create a dated raw folder for each field visit and record spring/DI measurements exactly as observed.
3. Once the team has confirmed site coordinates and a small collection buffer, acquire versioned Indian institutional base layers listed in the acquisition queue.
4. Only then create a staged, documented copy for cleaning or GIS processing.

## India-first collection routes

- NRSC Bhoonidhi, CartoDEM 30 m: https://bhoonidhi.nrsc.gov.in/bhoonidhi-api/
- NRSC Bhuvan, LULC/geomorphology/lineament WMS: https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms
- GSI Bhukosh geology and structures: https://bhukosh.gsi.gov.in/Bhukosh/Public
- India Meteorological Department rainfall data: https://mausam.imd.gov.in/
- ICAR-NBSS&LUP soils: verify an appropriate released Uttarakhand layer before use.

For this project, “open” will be recorded honestly as one of: **open service**, **free download with account**, **request/approval required**, or **not available for reuse**. It does not mean every government layer is automatically downloadable or current enough for field-scale conclusions. Non-Indian global layers are deferred unless an Indian source is unavailable and WATSAN agrees to the fallback.

## Coordinate-based LULC lookup

The required output is one documented LULC record per spring point, not a visual judgement from a basemap. The proposed order is:

1. Preserve the original latitude/longitude and assign a stable point ID.
2. Query a documented IIRS GeoHimalaya LULC layer at that coordinate, saving the source layer, version/date, class/code, legend, query time and no-data result.
3. Cross-check a small sample against an NRSC Bhuvan LULC reference layer and satellite imagery; record disagreement rather than force a match.
4. Stage the results only after the team accepts the pilot. The original `lulc` field remains untouched.

## Himmotthan source track

Himmotthan’s public materials describe a Spring Information System developed with the Uttarakhand Space Application Centre and an inventory/monitoring programme. This is a high-value independent source, particularly for Tehri, but we will obtain it only through an authorised extract with a data dictionary and reuse terms. The exact request is in `docs/source-register/himmotthan-data-request.md`.

Record the exact download URL, query/AOI, licence, timestamp, checksum and coordinate reference system at intake. For any field record, record the site, date, source type and measurement conditions. Do not silently replace an original file or invent a missing value.

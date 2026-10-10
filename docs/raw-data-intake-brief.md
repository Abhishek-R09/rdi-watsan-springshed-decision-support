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
3. Once the team has confirmed site coordinates and a small collection buffer, download versioned, authoritative base layers listed in the acquisition queue.
4. Only then create a staged, documented copy for cleaning or GIS processing.

## Official collection routes

- Copernicus DEM GLO-30: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- ESA WorldCover 2021 v200: https://esa-worldcover.org/en/data-access
- CHIRPS v3: https://chc.ucsb.edu/data/chirps3
- GSI Bhukosh: https://bhukosh.gsi.gov.in/Bhukosh/Public
- NRSC Bhuvan WMS: https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms
- FAO Harmonized World Soil Database v2.0: https://www.fao.org/land-water/resources/tools/databases/hwsd/en

Record the exact download URL, query/AOI, licence, timestamp, checksum and coordinate reference system at intake. For any field record, record the site, date, source type and measurement conditions. Do not silently replace an original file or invent a missing value.

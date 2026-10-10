# Data gap analysis and public-layer enrichment (v1)

Date: 2026-10-10. Input: `data/01_staged/common/csv/spring_records_common_v1.csv`, which has 1,842 records. Output: `data/02_processed/spring_features/`.

## 1. What the common file was missing

The table shows the share of records with a value, by source.

| Field | WATSAN (299) | Atlas annexure (948) | Himmotthan (542) | Literature (53) | Gap |
|---|---|---|---|---|---|
| Coordinates | 100% | 100% | 100% | 17 of 53 | Rathi (35) and Mathamali have none; 3 Atlas coordinates are typing errors |
| Elevation | 100% | 100% | 92% | 17 of 53 | Small |
| Discharge | 100% (text estimates) | **0%** | 99% (one-off) | 53 of 53 | No dated, repeated measurements anywhere except 10 Atlas profiles and Mathamali |
| Slope / aspect | 100% | **0%** | 92-99% | 7 of 53 | Atlas has none |
| Land use | 100% (code mislabelled) | **0%** | 92% | 0 | Mostly missing or unreliable |
| Rainfall | 100% | **0%** | **0%** | 17 of 53 | Mostly missing |
| Lithology / rock type | 100% (text) | **0%** | 92% | 17 of 53 | Atlas has none; no map-based geology for any source |
| Geological structure / lineaments | 100% (text) | **0%** | **0%** | 16 of 53 | No distance-to-lineament for any record |
| Soil | **0%** | **0%** | **0%** | 0 | Missing everywhere |
| Recharge / springshed area | 100% (estimates) | **0%** | **0%** | 52 of 53 | Only the Atlas profiles, Rathi and Chamba have delineated areas |
| Water quality (pH, TDS) | **0%** | **0%** | 99% | 10 of 53 | WATSAN and Atlas have none |
| Seasonality / variability | 100% (text labels) | **0%** | **0%** | 11 of 53 | No discharge time series except 10 Atlas profiles and Mathamali |
| Dependency (households, use) | **0%** | **0%** | **0%** | 0 | Not in any source |
| DI / recharge interventions | 0% | 0% | 0% | 18 of 53 | Only Chamba, Mathamali and the Atlas profiles |

Two problems are about data quality rather than gaps:
- **Duplicates across sources.** 217 groups of 448 records sit within 30 m of each other. 150 of these groups pair an Atlas row with a Himmotthan row, so the file probably holds about 1,570 distinct springs, not 1,803.
- **WATSAN values.** WATSAN elevations match the DEM to within about 5 m, which suggests they were themselves taken from a DEM. 9 WATSAN points fall on water pixels in WorldCover. Recharge areas and discharge are text estimates such as "55–65" or "~2–8 lpm dry".

## 2. What public layers could fill, and what was reached

| Layer asked for | Status | What was used |
|---|---|---|
| 30 m DEM | **Done** with Copernicus GLO-30 (AWS open data) | Elevation, slope, aspect, 500 m mean slope, 1 km relief, upslope relief, topographic position |
| CartoDEM (NRSC Bhoonidhi) | Not reached: needs a Bhoonidhi login | Copernicus is the substitute; the two are comparable at 30 m |
| Land use | **Done** with ESA WorldCover 2021 v200, 10 m (AWS open data) | Class at the spring, majority class and class shares within 500 m |
| Bhuvan LULC 1:50k | Not reached: Bhuvan is blocked from this environment and download needs a request | — |
| Rainfall | **Done** with CHIRPS v2 annual and monthly 2018-2025, as republished by FAO WaPOR v3 (~5 km) | Mean, minimum, maximum, year-to-year variation, monsoon share, dry-season rain, plus FAO reference ET0 and an aridity index |
| IMD 0.25° gridded rainfall | Not reached: imdpune.gov.in is blocked from this environment | — |
| Soil | **Done** with the FAO/IIASA Harmonized World Soil Database v2.0 (~1 km) | Dominant soil (WRB), drainage, available water capacity, topsoil sand/silt/clay, texture, coarse fragments, organic carbon |
| ISRIC SoilGrids 250 m | Not reached: blocked from this environment | — |
| Geology and lineaments (GSI Bhukosh, Bhuvan) | **Not reached**: Bhukosh needs a registered login and both sites are blocked here | The `geology_lithology_gsi` and `distance_to_lineament_m` columns exist but are blank |

After this step, 1,803 of 1,842 records (98%) have every terrain, land-cover, rainfall and soil value. The other 39 records have no usable coordinates.

## 3. What the processed file is (and isn't)

`spring_features_v1.csv` has one row per common-file record, with 67 columns:
- Cleaned identity: district spellings unified, coordinates parsed, coordinate status and precision, and a co-located group id for likely duplicates.
- Numbers parsed from the source text: elevation, discharge low/high, recharge-area low/high, rainfall, slope, TDS, pH. There are also two clearly named unit conversions: Rathi m3/day to L/min, and km2 to ha.
- Layer values for terrain, land cover, rainfall/ET0 and soil.
- `processing_notes` per row, for example a rounded coordinate or a DEM vs source elevation gap of more than 150 m (77 records).

Every column is defined in `spring_features_v1_data_dictionary.csv`. Fill rates by source are in `spring_features_v1_coverage_pct.csv`.

Limits to keep in mind:
- **Buffers are not recharge zones.** Layer values describe the pixel at the coordinate or a circle around it. They are not values for the spring's real recharge area, which is usually upslope. Module B should replace the 500 m circle with the delineated zone once it exists.
- **Rainfall is coarse.** CHIRPS (~5 km) and ET0 (~30 km) smooth out local differences. Source rainfall figures are on average 77 mm (WATSAN), 298 mm (Atlas profiles) and 431 mm (Chamba) below CHIRPS.
- **Soil varies little.** At HWSD's ~1 km scale, most springs fall in the same soil unit: 78% are Dystric Cambisols with loam topsoil and about 20% clay. Treat soil as context, not as a variable that tells springs apart.
- **Non-commercial licences.** WaPOR (CC BY-NC-SA 4.0) and HWSD (CC BY-NC-SA 3.0 IGO) allow only non-commercial use. That is fine for this project, but it needs attribution in reports.

## 4. Gaps that remain and how to close them

| Gap | Best route | Who |
|---|---|---|
| Geology (lithology map unit) and distance to lineaments | Register on GSI Bhukosh and download the 1:2M (or 1:50k where available) lithology and lineament shapefiles for Uttarakhand. Place them in `DOCC/Data/Bhukosh/` and they will be joined by the same script | Rajat (one-time login) |
| CartoDEM check | Optional. Download the Bhoonidhi CartoDEM tiles for Chamba and Satpuli and compare them with Copernicus | Rajat |
| IMD rainfall | Optional. The IMD 0.25° NetCDF from imdpune.gov.in, used to cross-check CHIRPS | Rajat |
| Repeated, dated discharge (dry and wet season) | Field survey (SRC-008 protocol), plus RDI/WATSAN monitoring records and Himmotthan MIS (AQ-003, AQ-012) | Team with WATSAN |
| Household dependency and use | Field survey / RDI village records (for example, the Malan table) | Team with WATSAN |
| DI before/after data | RDI monitoring records for the Chamba and Gairsain handpumps | WATSAN |
| Real recharge areas | Field hydrogeology at pilot springs, or Module B estimates checked against the 10 Atlas profiles, Rathi and Chamba | Team |
| Duplicates | Review the `colocated_group_id` pairs (mostly Atlas with Himmotthan) and pick one master record per spring | Team |
| Rathi and Mathamali coordinates | Ask NIH Roorkee or the authors | Team |

## 5. Rebuilding

```
pip install rasterio numpy access-parser
python scripts/build_spring_features.py --cache .layer_cache   # downloads about 1.3 GB of layers on first run
python scripts/export_hwsd_tables.py .layer_cache/hwsd/HWSD2.mdb  # only if the HWSD CSV tables are missing
```

Layers were accessed on 2026-10-10. URLs, versions, resolutions and licences are in `spring_features_v1_metadata.json`.

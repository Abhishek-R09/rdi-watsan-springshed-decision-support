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
| Geological structure / lineaments | 100% (text) | **0%** | **0%** | 16 of 53 | No distance-to-lineament for any record (now filled from DEM lineaments; see section 2) |
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
| CartoDEM (NRSC Bhoonidhi) | **Done** with 14 tiles Rajat downloaded by hand | Elevation and slope as a cross-check on Copernicus |
| Land use | **Done** with ESA WorldCover 2021 v200, 10 m (AWS open data) | Class at the spring, majority class and class shares within 500 m |
| Bhuvan LULC 1:50k | Not reached: Bhuvan is blocked from this environment and download needs a request | — |
| Rainfall | **Done** with CHIRPS v2 annual and monthly 2018-2025, as republished by FAO WaPOR v3 (~5 km) | Mean, minimum, maximum, year-to-year variation, monsoon share, dry-season rain, plus FAO reference ET0 and an aridity index |
| IMD 0.25° gridded rainfall | **Done** for 2025 only, from the file Rajat downloaded | Annual total, monsoon share, rainy days, wettest day |
| Soil | **Done** with the FAO/IIASA Harmonized World Soil Database v2.0 (~1 km) | Dominant soil (WRB), drainage, available water capacity, topsoil sand/silt/clay, texture, coarse fragments, organic carbon |
| ISRIC SoilGrids 250 m | **Done** for 0-5 cm, from 5 exports Rajat downloaded | Clay, silt, sand, bulk density, organic carbon density |
| Lineaments | **Done** as DEM-derived candidates (`scripts/extract_dem_lineaments.py`) | Distance to nearest lineament and lineament density within 1 km |
| Geology and faults (GSI Bhukosh) | **Not reached**: the Bhukosh site was not working on 2026-10-10 | `geology_lithology_gsi` and `distance_to_gsi_fault_m` exist but are blank |

After this step, 1,803 of 1,842 records (98%) have every terrain, land-cover, rainfall and soil value. The other 39 records have no usable coordinates.

### Hand-downloaded layers (added later on 2026-10-10)

Rajat downloaded CartoDEM, IMD 2025 rainfall and SoilGrids by hand. The raw files stay in `DOCC/Data/` and are not committed; `build_spring_features.py --local-layers DIR` reads them. What they show:
- **CartoDEM** covers 1,780 springs (no tile for the 23 Kangra springs). It sits a steady ~44 m below Copernicus (middle 90%: 26-58 m). That matches the geoid height in this region, so the tiles are most likely ellipsoidal heights, not sea-level heights. Slopes agree with Copernicus (median 20.8 vs 21.4 degrees). Use Copernicus as the main DEM.
- **IMD 2025** is a single year at ~25 km. Median 1,436 mm against a CHIRPS 2018-2025 mean of 1,817 mm, and some hill cells fall to ~560 mm. IMD grids are thin on hill stations, so treat these as a cross-check, not a replacement.
- **SoilGrids** files arrived unnamed (`out.tif` to `out (4).tif`). Organic carbon density was confirmed by Rajat; the other four were identified from their values (bulk density 0.96-1.55 g/cm3; clay + silt + sand add to a median 99.2%). Depth 0-5 cm is assumed from the viewer default. At 250 m they separate springs much better than HWSD: 82 distinct clay values against 4.
- **DEM lineaments**: 26,672 straight terrain lines of at least ~0.9 km from the Copernicus DEM. Median distance from a spring to the nearest is 618 m; median density within 1 km is 0.3 km/km2. These are unvalidated candidates: some are faults or fracture-controlled valleys, others are ordinary ridges. Copernicus was used rather than CartoDEM because it covers all spring tiles and has fewer artefacts.

## 3. What the processed file is (and isn't)

`spring_features_v1.csv` has one row per common-file record, with 81 columns:
- Cleaned identity: district spellings unified, coordinates parsed, coordinate status and precision, and a co-located group id for likely duplicates.
- Numbers parsed from the source text: elevation, discharge low/high, recharge-area low/high, rainfall, slope, TDS, pH. There are also two clearly named unit conversions: Rathi m3/day to L/min, and km2 to ha.
- Layer values for terrain, land cover, rainfall/ET0, soil and DEM lineaments.
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
| Geology (lithology map unit) and faults | When Bhukosh works again: lithology, faults (and shear zones), optionally folds, as shapefiles for Uttarakhand, into `DOCC/Data/Bhukosh/`. Alternatives meanwhile: HimaTibetMap or GEM Global Active Faults for the major thrusts; USGS Geologic Map of South Asia (coarse) | Rajat (one-time login) |
| Check DEM lineaments | Compare with GSI faults once available, or spot-check against imagery at pilot springs | Team |
| IMD rainfall, more years | Optional. Earlier IMD years would give a long-term mean to compare with CHIRPS | Rajat |
| Repeated, dated discharge (dry and wet season) | Field survey (SRC-008 protocol), plus RDI/WATSAN monitoring records and Himmotthan MIS (AQ-003, AQ-012) | Team with WATSAN |
| Household dependency and use | Field survey / RDI village records (for example, the Malan table) | Team with WATSAN |
| DI before/after data | RDI monitoring records for the Chamba and Gairsain handpumps | WATSAN |
| Real recharge areas | Field hydrogeology at pilot springs, or Module B estimates checked against the 10 Atlas profiles, Rathi and Chamba | Team |
| Duplicates | Review the `colocated_group_id` pairs (mostly Atlas with Himmotthan) and pick one master record per spring | Team |
| Rathi and Mathamali coordinates | Ask NIH Roorkee or the authors | Team |

## 5. Rebuilding

```
pip install rasterio numpy access-parser
pip install scipy scikit-image shapely pyproj                   # for the lineament step
python scripts/build_spring_features.py --cache .layer_cache   # downloads about 1.3 GB of layers on first run
python scripts/extract_dem_lineaments.py --cache .layer_cache  # needs the DEM tiles from the step above
python scripts/build_spring_features.py --cache .layer_cache --local-layers .local_layers
python scripts/export_hwsd_tables.py .layer_cache/hwsd/HWSD2.mdb  # only if the HWSD CSV tables are missing
```

`.local_layers/` holds the hand downloads: `Bhoonidhi/*.zip`, `IMD/*.nc` and `SoilGrids/{clay,silt,sand,bdod,ocd}_0-5cm_mean.tif`. Without it those columns stay blank. Layers were accessed on 2026-10-10. URLs, versions, resolutions and licences are in `spring_features_v1_metadata.json`.

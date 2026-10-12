# Literature enrichment of the common spring file (v1)

Date: 2026-10-10. Adds 53 spring rows from papers and reports to `data/01_staged/common/csv/spring_records_common_v1.csv` (1,789 → 1,842 rows).

## How it is stored

- The existing 31 columns and 1,789 rows are unchanged. 18 new columns are appended after `source_notes`; they are blank for the WATSAN, Spring Atlas annexure and Himmotthan rows.
- Every added value has a row in `data/01_staged/literature/csv/literature_spring_values_long_v1.csv` with its unit, page/table locator and status (`measured`, `reported`, `approximate`, `delineated_estimate`, `derived_by_source`, `descriptive`).
- Values are typed as printed. No unit conversion (m3/day stays m3/day, km2 stays km2), no interpolation, no merging. Thousands separators were removed from the Chamba numbers.
- `candidate_match_record_ids` points to existing rows that look like the same spring. These are leads to check, not merges.
- The transcriptions live in `scripts/literature_spring_records.py`; `scripts/stage_watsan_and_spring_atlas.py` appends them when it rebuilds the common file, and `scripts/build_literature_workbooks.py` rebuilds the common and literature `.xlsx` files.

## What was added

| Source | Rows | Record IDs | Main values added |
|---|---|---|---|
| Rathi et al. 2021, Tables 1-2 (SRC-011) | 35 (20 Chandrabhaga, 15 Danda) | RAT-SPR-0001 to 0035 | Max flow (m3/day, measured 10-yr average), springshed area (km2), springshed min/max elevation, clubbed-spring groups and % share |
| RDI Chamba Spring Assessment Report (SRC-003) | 7 | RDI-SPR-0001 to 0007 | Approx. coordinates, spring elevation, micro-watershed area and elevation range, slope, aspect, lithology, spring discharge range, nearby DI handpump discharge, aquifer type |
| Daniel et al. 2021, Table 6 and Section 5 (SRC-012) | 1 (Mathamali) | DAN-SPR-0001 | 75% dependable flow 2014-2016, recharge works since 2010-11, vulnerability index 2.3 |
| Spring Atlas of Uttarakhand, representative spring profiles, PDF pp. 16-55 (SRC-008) | 10 | ATP-SPR-0001 to 0010 | Coordinates, elevation, rainfall, pH, TDS and other water quality, discharge, spring type, geology, recharge area (ha), recharge-area slope/aspect, rainfall-discharge series before and after recharge works, works done |

## What could not be extracted

- **Rathi 2021:** no spring coordinates or outlet elevations are published, so these rows have no geometry. Springshed areas were tuned to fit the area-flow regression, so they cannot validate that same relation. The regression coefficients are only shown in a figure (Fig. 5), not printed.
- **Daniel 2021:** no coordinates for Mathamali. The region-level stressor values in Table 6 describe Tehri/Uttarakhand, not individual springs, so they are only quoted in the index text.
- **Spring Atlas profiles:** sampling dates and monitoring methods are not given. Hydrographs are images; only numbers printed in the text or tables were taken. Basgaon (4.08 vs 8.5 ha) and Naghar (7 vs 12 ha) state two different recharge areas; both are recorded and flagged.
- **Chamba report:** coordinates are rounded to about 1 km, and discharge dates/methods are not stated. Balench and Paniyar Dhar are labelled "Arakot region", but their coordinates fall near Chamba. Needs a check with WATSAN.
- **ICIMOD Science in Spring Restoration (2025):** gives only village-level counts (e.g. Moldhar, Tehri: 7 springs; Ghurdauri, Pauri: 4) and percentage changes for Wata-1/2 in Manipur. There are no spring-level values.
- **Nijesh et al. 2024 (Khulgad, Kosi):** springs are shown on maps only; no spring table.
- **WaterRecharge AIML slides:** the Malan springshed village table is an image. Only model weights and scores are text.
- **Revival of 13 Defunct Handpumps report (Gairsain):** lists handpump sites only. It has no coordinates or before/after measurements.
- **NMHS report, ICIMOD manual 2018, SOP, NITI/IWMI resource book, HimalDoc leaflet, Chen 2020, Wei 2022:** these are methods, guidance or work outside India, with no Uttarakhand spring-level data.

## Open points for the team

- Resolved 2026-10-10: the source register now uses SRC-007 for Himmotthan and SRC-008 for the Spring Atlas, matching the staged data and logs. The old placeholders moved to SRC-016 (Indian institutional layers) and SRC-017 (field survey).
- The original papers and the RDI report are not committed: one is copyrighted and one is an internal report, and the repository is public. They stay in the team's DOCC folder. WATSAN confirmed on 2026-10-12 that the Chamba report values can stay in this public repository.
- `build_common_spring_workbook.mjs` still describes 31 columns. If it is re-run, it will overwrite the common `.xlsx` without the literature sheets. Run `build_literature_workbooks.py` after it.

# Staged data layout

Each source has a separate folder and the same structure:

- `csv/` - machine-readable staged tables.
- `xlsx/` - the matching review/share workbook.
- `metadata/` - generated extraction metadata where applicable.

`common/` contains the combined source-traceable master table. It is an append of source records, not a deduplicated spring inventory. Raw source files belong in `../00_raw/<source>/` and must not be edited.

`literature/` holds spring rows transcribed from papers and reports (Rathi et al. 2021, Daniel et al. 2021, the RDI Chamba Spring Assessment Report and the Spring Atlas representative-spring profiles). `literature_spring_values_long_v1.csv` gives the source page/table and measured-or-estimated status of every value. See `docs/literature-enrichment-notes.md`.

`ngdr_geology/` holds separate NGDR fault-line, fold-line, and lithology-polygon attribute extracts. Their original geometry remains unchanged in `data/00_raw/ngdr_geology/`; the staged CSV/XLSX rows preserve a GeoJSON feature locator and bounds only. They have not been spatially joined to spring records.

Rebuild order: `python scripts/stage_watsan_and_spring_atlas.py`, `python scripts/build_literature_workbooks.py`, then `python scripts/stage_ngdr_geology.py` and `node scripts/build_ngdr_geology_workbooks.mjs`.

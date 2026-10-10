# Staged data layout

Each source has a separate folder and the same structure:

- `csv/` - machine-readable staged tables.
- `xlsx/` - the matching review/share workbook.
- `metadata/` - generated extraction metadata where applicable.

`common/` contains the combined source-traceable master table. It is an append of source records, not a deduplicated spring inventory. Raw source files belong in `../00_raw/<source>/` and must not be edited.

`literature/` holds spring rows transcribed from papers and reports (Rathi et al. 2021, Daniel et al. 2021, the RDI Chamba Spring Assessment Report and the Spring Atlas representative-spring profiles). `literature_spring_values_long_v1.csv` gives the source page/table and measured-or-estimated status of every value. See `docs/literature-enrichment-notes.md`.

Rebuild order: `python scripts/stage_watsan_and_spring_atlas.py`, then `python scripts/build_literature_workbooks.py`.

Processed per-spring features (terrain, land cover, rainfall, soil from public layers) are built from the common file by `scripts/build_spring_features.py` into `data/02_processed/spring_features/`. See `docs/data-gap-analysis.md`.

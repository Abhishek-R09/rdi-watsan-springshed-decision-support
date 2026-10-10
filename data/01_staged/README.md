# Staged data layout

Each source has a separate folder and the same structure:

- `csv/` - machine-readable staged tables.
- `xlsx/` - the matching review/share workbook.
- `metadata/` - generated extraction metadata where applicable.

`common/` contains the combined source-traceable master table. It is an append of source records, not a deduplicated spring inventory. Raw source files belong in `../00_raw/<source>/` and must not be edited.

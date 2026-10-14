# Project 1 — Spring vulnerability, recharge-zone and DI support

Private working repository for the SRHU/HIHT RDI WATSAN DoCC Project 1 team.

## What belongs here

This repository holds the reproducible project record: raw inputs, field records, source metadata, scripts, staged and processed data, and handover outputs. It supports three connected modules:

1. transparent spring-vulnerability scoring;
2. a provisional, field-verifiable candidate recharge-zone estimate; and
3. a best-case Direct Injection (DI) water-balance estimate.

The tool is decision support, not a substitute for hydrogeological verification. DI estimates are upper-bound planning calculations until monitoring permits calibration.

## Data flow

`data/00_raw` → `data/01_staged` → `data/02_processed` → `data/03_outputs`

- **00_raw:** received or downloaded files, unchanged after intake. Add a register entry first.
- **01_staged:** standardised copies with source, date, units and transformations recorded.
- **02_processed:** reproducible analysis-ready files. Most are generated locally; the small per-spring tables (`spring_features/`, `spring_master/`) and the DEM lineament file are committed so the team can open them without rebuilding. Start with `data/02_processed/spring_master/spring_master_v1.xlsx`.
- **03_outputs:** maps, tables and tool exports; generate them from scripts and staged inputs. Module A (vulnerability score) results are in `data/03_outputs/module_a/`; method and how to run it: `docs/module-a-vulnerability.md`. For how Modules A, B and C fit together, see `docs/module-contract.md`. To run Module A on your own computer, see `docs/run-module-a-locally.md`.

Do not put credentials, personal contact details, consent-sensitive photos, or unapproved community data in the repository.

## Start here

1. Add every received/downloaded file to `docs/source-register/source-register.csv` before analysis.
2. Store it unchanged in `data/00_raw/<source-id>/`.
3. Record every cleaning or conversion in `docs/source-register/transformation-log.csv`.
4. Keep observed data, community recall, staff hypotheses and project calculations distinct.

The current register is an intake inventory, not an endorsement that each data source is suitable for modelling.

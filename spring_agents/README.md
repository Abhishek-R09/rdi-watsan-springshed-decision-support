# Agent runtime, first connected pass

This Python package executes the [agent specifications](../agents/README.md) without a model API or per-request data download. It implements coordinate checks (`R-ORC-01`, `R-SPR-01`), user bucket-reading arithmetic (`R-SPR-03`), local snapshot availability checks (`R-ORC-02`, `R-TER-01`), current contract and run lineage (`R-LIN-01`–`04`), and the applicable unavailability, verification and presentation gates. Each output uses its exact `AG-...` ID and is saved as a new JSON record under `data/03_outputs/assessments/<run_id>/<agent_id>/`.

**Vulnerability (Module A).** When a request sets `include_vulnerability: true`, the [Vulnerability Agent](../agents/vulnerability.md) (`AG-VUL`, in `vulnerability.py`) runs Module A on the same point, in either mode. It reads `location.elevation_m` (optional) and `field_form.vulnerability_answers`, and its result reaches `AG-COM.assessment_summary` under `vulnerability`. Module A reads its own layer cache (`SPRING_LAYER_CACHE`, `SPRING_LOCAL_LAYERS`), which is not yet an approved snapshot; each result records this as issue `R-VUL-03`. The open layers stay in memory between assessments in one process.

The runtime deliberately returns `unavailable` for DEM routing, catchment polygons and springshed interpretation. The [Terrain](../agents/terrain.md), [Catchment](../agents/catchment.md) and later specialist specifications do not contain approved executable spatial methods. The registered `SRC-018` DEM cache is not present in this checkout. This is a connected decision-support skeleton, not a delineation engine or an approved scientific rulebook.

`spring_agents.catchment.mask_area` implements only the defined `R-CAT-03`/`R-CAT-04` cell-area arithmetic and edge/no-data flags for a supplied, already approved metric-grid mask. It does not select drainage cells or create a polygon, so it is not invoked by the current run.

Run a contract check:

```powershell
python scripts/run_agent_assessment.py --check-contracts
```

Run an assessment with a user-created JSON file:

```powershell
python scripts/run_agent_assessment.py --input path/to/submission.json
```

Use the Python interpreter in the project environment. On Windows, confirm that `python` resolves to the intended installation or virtual environment before running these commands.

The input object requires `location.latitude`, `location.longitude`, and `location.crs` = `EPSG:4326`. `mode` is `catchment` (default) or `springshed`; `spring_id` is optional. `field_form.bucket_readings` is an optional list of objects with positive `volume_L` and `time_s`, plus date, conditions and rainfall context supplied by the user. The unchanged submitted JSON is preserved inside the run directory. A valid location is never silently shifted to a stream.

The field-facing interface is the standalone [Preact preview](../interface/README.md); it does not invoke this package yet. An older [app.py](../app.py) Streamlit prototype invokes this package directly. Once Streamlit is installed in the project environment, run `streamlit run app.py` to use that prototype. Streamlit is absent from the current bundled Python runtime, so it has not been launched here; the standard-library CLI remains executable. No Google Maps credential or provider API is required for the current unavailable-boundary view.

The snapshot selector only reads `data/02_processed/snapshots/active.json` when an explicitly approved snapshot exists. Its interface requires `snapshot_id`, `approval_status: approved`, and `dem` with `source_id` (`SRC-018` or reviewed `SRC-022`), `coverage_bbox_wgs84` (`[west,south,east,north]`), `tiles` with relative file paths and SHA-256 values, and `transformation_ids` (an explicit empty list if the registered raw tile was used without conversion). This describes a future intake contract, not an approval for any currently registered DEM or a complete routing configuration. Do not create an active snapshot merely to suppress an unavailable status.

No existing raw/staged file is modified. The user-facing summary keeps missing area and boundary as null and retains the reason and next field check. `AG-LIN.contract_map` describes declared links; `AG-LIN.run_trace` describes the recorded path of that assessment. A `complete` lineage trace does not mean a complete polygon or hydrogeological validation.

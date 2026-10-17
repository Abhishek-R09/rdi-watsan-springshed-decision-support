# Render field-pilot deployment

Prepared 17 October 2026. This prepares the existing Modules A, B and C for one field user at a time. It does not change their hydrological rules, approve a map snapshot, publish field records, or create a paid service.

## What has been prepared

- `render.yaml`: one **Free** Docker web service in Singapore, with automatic redeployment disabled and no paid disk/database.
- `Dockerfile`: builds the React interface and installs the pinned Python/GIS runtime, then runs as an unprivileged user. The interface and APIs share one HTTPS address.
- `scripts/render_app.py`: production WSGI adapter reusing the existing `Tool`; browser password prompt, JSON errors, unauthenticated health probe, and a one-assessment gate.
- `deploy/gunicorn.conf.py`: one worker, four request threads and a ten-minute worker timeout. Health and terrain can respond while an assessment runs. This timeout does not guarantee that every external proxy will allow a ten-minute request.
- Private S3-compatible storage integration: restores the prepared map archive on startup and saves each assessment as one JSON object containing the original request, result and readable reports.
- Hosted builds disable automatic illustrative/demo results. A connection failure disables assessment and asks the user to reconnect.
- Failed archive uploads leave the calculated result visible, with an unsaved warning and JSON download button. An uploaded result receives an archive key in its response.
- Smaller hosted cache limits, a single terrain reader and single-threaded numerical libraries reduce memory without changing scores or formulas. Local defaults remain unchanged.

## Current verification and limitations

The initial Windows hosted-adapter benchmark peaked at **461.3 MiB process RSS**. On 17 October the user reported that the first Render assessment exceeded its memory limit and restarted. That local RSS check did not provide sufficient evidence of deployment headroom.

After the memory changes below, the local benchmark completed all three modules with synthetic field answers at the existing Nauli Dhara reference coordinate, alongside **144 concurrent visual-terrain requests**. It recorded **22.2 seconds including process startup** and **428.6 MiB peak process RSS**. Comparing A/B/C outputs with the earlier compiled run found no differences, including 9,832 numeric values checked with 1e-9 tolerance. **34 deployment/module checks passed.** These remain Windows process measurements, excluding Gunicorn's master process and total Linux cgroup usage. The revised deployment still needs a successful Render cold run; larger map windows and additional datasets may require more than 512 MB.

Docker is not installed on this machine, so an image build and Render cold-start assessment remain mandatory before taking this deployment to the field. A successful local test is not a claim that Render Free is sufficient.

The image installs `libexpat1`, required by the Rasterio/GDAL native libraries (`libexpat.so.1`), as well as `libgomp1`. `deploy/check_runtime.py` now runs as the unprivileged application user during the Docker build. It checks GIS imports, an in-memory GeoTIFF with a coordinate reference system, backend initialisation, the spring catalogue, recharge rules and literature fit, and the built frontend. A missing native library therefore fails the build instead of repeatedly crashing the deployed worker. This check uses no cloud credentials and downloads no maps; it does not replace the real hosted assessment and archive test.

Preparation checks passed: 32 deployment/module tests; the hosted frontend production build; the Blueprint against Render's published JSON schema; Linux x86-64/Python 3.12 binary dependency resolution; and whitespace validation. The updated map rendered in the local browser without recorded console errors. Storage tests used a fake client: no external bucket or live persistence has been verified yet.

The locally prepared map bundle is `deploy/artifacts/pilot-v1.tar.gz`, **328,186,107 bytes**, with SHA-256:

```
36edf7bdc7c9ac39ef3b67a15101f6dafdd2ac166d5443811c2e0251912cbbc3
```

Its adjacent `.manifest.json` records every file's bytes and checksum. It contains the existing DEM, WorldCover and cached WaPOR rainfall/evaporation files. It excludes field visits, photographs, reports, documents, assessment histories, building-response caches and web terrain caches.

**Missing here:** `IMD`, `SoilGrids` and `Bhoonidhi` (CartoDEM) manually supplied layers. **No approved map snapshot exists here.** The application can run its existing fallbacks and missing-data handling, as it does locally, but this bundle is not equivalent to the complete dataset on Rajat's laptop. It is not a reviewed offline field data release. Coverage of every planned Satpuli/Chamba coordinate has not been established by one Nauli test.

Geology, reference features, the spring list, lineaments and literature sizing records are copied from explicit repository paths into the image. They are not regenerated. The Docker context excludes unrelated raw sources and private field-visit scripts. Keep the repository, image and data bucket private, and review source permissions before uploading analytical data. A private object store does not itself grant redistribution rights.

## 1. Assemble the intended field maps

Run from the `Application` repository. Python must have the existing GIS dependencies installed:

```powershell
$env:SPRING_LAYER_CACHE='PATH_TO_MapCache'
$env:SPRING_LOCAL_LAYERS='PATH_TO_Data'
python deploy/prepare_data.py --output deploy/artifacts/pilot-v2.tar.gz
```

The script copies existing analytical layers unchanged into a compressed bundle. It does not download maps, import field records, approve a snapshot or upload anything. Do not overwrite a versioned bundle. Read `missing_layer_families` and the file inventory in the adjacent manifest.

For a reviewed, download-free assessment dataset, use the existing `module_a_snapshot.py` prepare/verify/approve workflow after the intended coverage and evidence have been reviewed. The deployment preparation does not mark anything approved on your behalf. The packaging script includes an existing approved active manifest only after verifying it. Its referenced repository tables must match the Git version deployed.

## 2. Provide private object storage

Render Free cannot retain new local files over sleep/restart, so the complete pilot needs storage elsewhere. The adapter supports standard S3-compatible object storage; it does not require Amazon specifically. Select an existing institutional account or an appropriate no-cost storage allowance and check its own limits. No provider account or bucket has been created by this preparation.

Use a private bucket for the map bundle and a private bucket for saved runs; they can be the same bucket with separate keys. Upload the reviewed bundle to `datasets/pilot-v1.tar.gz` (or change the configured key for the next version). Upload through that provider's dashboard or an authorised S3 client. Never commit the bundle or credentials to Git.

The server needs **read** permission on the configured map object and **write** permission under `runs/` in the assessment bucket. Do not grant public-read access. The application does not offer a history browser yet; retrieve saved assessment JSON files through the storage provider's private dashboard. Each object retains the inputs and all three reports for handover.

Map transfer happens at runtime, not during the image build. Render's local filesystem can disappear after inactivity, so waking the app may download the approximately 328 MB bundle again. This can add considerable startup time and storage-provider traffic. Reused extracted files are skipped only while the local checksum marker remains. Test a genuine sleep/wake cycle. A persistent paid disk or a privately built image containing the maps can remove this repeated download, but neither is configured in this Free blueprint.

## 3. Connect the repository to Render

1. Put the prepared source changes on a Git branch accessible to your Render account. No changes have been committed or pushed by this preparation.
2. In Render, choose **New → Blueprint**, connect the repository and select `render.yaml`.
3. Keep the service on **Free**. The Git repository root is this `Application` folder, so leave the root directory blank. A service name may need changing if already taken.
4. Enter the requested secrets in Render's dashboard; use HTTPS URLs for custom storage endpoints.

| Setting | Value |
|---|---|
| `SPRING_PILOT_USER` | Defaults to `watsan`; shared pilot login |
| `SPRING_PILOT_PASSWORD` | A strong password entered only in Render |
| `SPRING_S3_ENDPOINT` | Provider's HTTPS S3 endpoint; blank only when using native AWS S3 |
| `AWS_ACCESS_KEY_ID` | Scoped storage access key |
| `AWS_SECRET_ACCESS_KEY` | Scoped storage secret |
| `AWS_DEFAULT_REGION` | `auto` for providers that support it; actual bucket region for AWS |
| `SPRING_DATA_BUCKET` | Private bucket containing the bundle |
| `SPRING_DATA_KEY` | Exact bundle object key, default `datasets/pilot-v1.tar.gz` |
| `SPRING_DATA_SHA256` | SHA-256 from the selected bundle manifest |
| `SPRING_RUN_BUCKET` | Private bucket for assessment objects |
| `SPRING_REQUIRE_ARCHIVE` | Keep `1` for the field pilot |

Do not paste credentials into this guide or chat. The service refuses startup when its required deployment settings are missing. It also refuses an incorrect data checksum and unsafe archive paths. Startup requires downloading the selected bundle; a successful health response means the worker has started, not that every scientific dataset is complete or archive credentials have passed a live write test.

The browser asks for the shared pilot login. Authentication protects the interface, springs list, terrain and assessment APIs; `/api/health` is intentionally public for Render. Use Render's HTTPS address. This is basic single-team access, not a multi-user account/permission system.

## 4. Verify before a field visit

1. Check the build log and successful `/api/health`. Open the app and authenticate.
2. Run a known spring inside the prepared map coverage with representative field inputs and a DI site. Confirm actual A/B/C outputs, warnings and map overlays; do not accept a demo as a backend test.
3. Confirm `persistence.durable` is true in the assessment response and open the corresponding `runs/<run_id>.json` in private storage. Check request, result and all reports.
4. Restart the service. Confirm the earlier run still exists in storage; run a second assessment and verify it too.
5. Leave the service unused long enough to sleep, then repeat from a phone over mobile data. Record wake time, assessment time, memory, any out-of-memory restart and download traffic.
6. Try a failed archive upload in a controlled test. The app should retain the result and show the unsaved warning/download option. Restore valid credentials afterwards.
7. Test each planned field coordinate's coverage. Run the benchmark again after adding IMD/soil/CartoDEM. If memory exceeds the free limit, do not remove evidence silently to claim success: adjust data loading or choose a suitable host.

Keep a local application/workbook fallback. Remote hosting still needs a working field internet connection; this preparation does not make the web application fully offline.

## Local checks

### Memory settings for the 512 MB pilot

The Docker image disables Numba's runtime compilation (`NUMBA_DISABLE_JIT=1`),
limits GDAL's raster block cache to 8 MB, and limits glibc allocation arenas.
The routing and scoring algorithms and input precision are unchanged; interpreted
execution can be slower, especially for large catchments. Do not treat a passing
Windows RSS benchmark as proof that Render's entire Linux container fits in 512 MB.

With `SPRING_TERRAIN_SOURCE=public`, the authenticated terrain route redirects
the browser to the existing AWS Terrarium provider. This is display-only terrain;
assessments continue using the private cached Copernicus DEM. It avoids allocating
server-side terrain image buffers while assessing. Local runs retain their original
terrain path. The browser requires internet access to the public terrain provider.

`SPRING_LOG_MEMORY=1` prints process RSS, peak RSS and Linux cgroup memory after
each assessment module, without coordinates or credentials. Check these readings
on the first and subsequent Render assessments, alongside Render's memory graph.
If the service still runs out of memory, the free instance is not sufficient for
that workload; retain all evidence and use a larger instance or another host.

```text
pip install -r requirements-render.txt
pip install pytest psutil
python -m pytest tests/test_render_deployment.py tests/test_module_a.py tests/test_spring_tool.py
python deploy/benchmark.py
```

For a container check on a Docker-enabled machine:

```text
docker build -t spring-pilot .
docker run --rm --memory=512m --cpus=0.1 -p 10000:10000 --env-file .env spring-pilot
```

The private `.env` file supplies the settings above; it is excluded from Git and the Docker context. This starts a real connection to the selected storage provider. Inspect the image's capabilities with a real assessment, including raster format support for manually supplied layers. The benchmark writes under ignored `.deployment-benchmark/`; artefacts under `deploy/artifacts/` are also ignored.

## Hosting references

- [Render Free limitations](https://render.com/docs/free): sleep, temporary files, transfer and service limits.
- [Render compute plans](https://render.com/docs/compute-plans): Free provides 0.1 CPU and 512 MB RAM.
- [Render Docker deployments](https://render.com/docs/docker) and [Blueprint specification](https://render.com/docs/blueprint-spec).
- [MapLibre security advisory](https://github.com/maplibre/maplibre-gl-js/security/advisories/GHSA-jrc7-96c5-q579): map library updated to patched 6.4.1 during preparation; the audited frontend dependency tree then reported no known vulnerabilities.

Free hosting does not cover unlimited third-party basemap delivery, object-storage traffic or a guarantee of uptime. The existing map providers and source attributions are retained; provider-specific usage terms still apply.

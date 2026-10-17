FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY app/package.json app/package-lock.json ./
RUN npm ci
COPY app/ ./
ENV VITE_ALLOW_DEMO=false
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-render.txt ./
RUN pip install --no-cache-dir -r requirements-render.txt
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY data/00_raw/ngdr_geology/ ./data/00_raw/ngdr_geology/
COPY data/01_staged/literature/csv/literature_spring_records_common_v1.csv ./data/01_staged/literature/csv/
COPY data/02_processed/spring_features/ ./data/02_processed/spring_features/
COPY data/02_processed/spring_master/ ./data/02_processed/spring_master/
COPY data/02_processed/lineaments/ ./data/02_processed/lineaments/
COPY --from=frontend /build/dist ./app/dist
COPY deploy/ ./deploy/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    SPRING_LAYER_CACHE=/tmp/spring-data/layer_cache \
    SPRING_LOCAL_LAYERS=/tmp/spring-data/local_layers \
    SPRING_SNAPSHOT_DIR=/tmp/spring-data/snapshots \
    SPRING_RUNS_DIR=/tmp/spring-runs \
    NUMBA_CACHE_DIR=/tmp/numba OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    NUMBA_NUM_THREADS=1 NUMBA_DISABLE_JIT=1 GDAL_CACHEMAX=8 MALLOC_ARENA_MAX=2 \
    SPRING_TERRAIN_SOURCE=public SPRING_TERRAIN_READERS=1 SPRING_TERRAIN_CACHE=16 SPRING_LOG_MEMORY=1 \
    SPRING_FEATURE_CACHE=2 SPRING_ZONE_CACHE=1
RUN useradd --uid 10001 --create-home spring
USER spring
# Check native GIS libraries and required reference files before publishing the image.
# This needs neither cloud credentials nor a download of the private map bundle.
RUN python deploy/check_runtime.py
EXPOSE 10000
CMD ["python", "deploy/start_render.py"]

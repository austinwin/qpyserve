# QPyServe Spatial Lab — Kepler.gl + Python

A **real** browser WebGL map (Kepler.gl) and **real** backend geometry processing (Shapely + PyProj) integrated through QPyServe.

[**Live demo**](https://qpyserve-live-showcase.onrender.com)

## Architecture

- React + Kepler.gl 3.2.6 provides map interaction, layers, styling and filtering via WebGL.
- QPyServe serves the Vite production build and FastAPI routes from one origin.
- FastAPI validates GeoJSON (EPSG:4326) and runs geometry operations in **UTM zone 15N EPSG:32615** for metre-based calculations.
- The server returns GeoJSON (EPSG:4326) to the browser. The browser converts it into a new Kepler.gl dataset/layer.
- No Mapbox token is needed; the map uses a custom raster Carto basemap. Map tiles require internet access.

## Operations

POST /api/geoprocess:
- buffer — metres; per-feature or dissolved coverage
- density — metre-based square grid counts and average pressure (where available)
- hull — convex hull

GET /api/sample — deterministic **synthetic** Houston-area sites (not real Houston Water facilities).
GET /api/health — service info.
GET /api/source-files — allowlisted project files only.
GET /api/source?path=main.py — read allowlisted source files only.

Demo limits: 2500 features, 90k vertices, Texas Gulf geographic region. Uploaded collections are not stored server-side. **Do not use for engineering design, pressure analysis or utility operations.**

## Local

Node 20+, Python 3.10+:

\`\`\`sh
cd showcase
pip install -r requirements.txt
cd frontend && npm install && cd ..
python main.py
\`\`\`

## Deploy

Render Docker service using branch \`showcase/render-live-demo\`, Docker context \`showcase\`, Dockerfile \`showcase/Dockerfile\`, free plan. Browser and API served from the same public origin.

Heavy processing on shared free hosting is limited by memory and request timeout. For real workloads: async job queue, object storage, chunked ingest, and vector/PMTiles.

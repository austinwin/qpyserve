"""QPyServe + Kepler.gl geospatial processing demo, with public source allowlist."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from qpyserve import run

from geoengine import GeoInputError, process_features, sample_points

ROOT = Path(__file__).resolve().parent
STARTED = time.monotonic()
app = FastAPI(title="QPyServe Spatial Lab", version="1.1.0")

SOURCE_FILES = {
    "backend": ["main.py", "geoengine.py"],
    "frontend": [
        "frontend/src/App.jsx", "frontend/src/MapPanel.jsx",
        "frontend/src/main.jsx", "frontend/src/index.css",
        "frontend/public/basemap.json", "frontend/package.json",
    ],
    "deployment": ["Dockerfile", "requirements.txt"],
}
ALLOWED = set(sum(SOURCE_FILES.values(), []))


class ProcessRequest(BaseModel):
    operation: str = Field(pattern="^(buffer|density|hull)$")
    distance_m: float = Field(default=400, ge=10, le=2500)
    cell_m: float = Field(default=1200, ge=150, le=4000)
    dissolve: bool = True
    collection: dict | None = None


@app.get("/api/health")
def health():
    return {
        "status": "ok", "runtime": "QPyServe 0.4 + FastAPI",
        "spatial_engine": "Shapely + PyProj",
        "uptime_seconds": round(time.monotonic() - STARTED, 1),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/sample")
def sample(count: int = 850):
    if not 100 <= count <= 2000:
        raise HTTPException(status_code=400, detail="Sample count must be 100–2000")
    return sample_points(count)


@app.post("/api/geoprocess")
def geoprocess(request: ProcessRequest):
    started = time.perf_counter()
    collection = request.collection if request.collection is not None else sample_points()
    try:
        result = process_features(
            collection, operation=request.operation, distance_m=request.distance_m,
            cell_m=request.cell_m, dissolve=request.dissolve,
        )
    except GeoInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["metadata"]["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result


@app.get("/api/source-files")
def source_files():
    return {group: [{"id": p, "name": p.split("/")[-1]} for p in paths]
            for group, paths in SOURCE_FILES.items()}


@app.get("/api/source")
def source(path: str):
    if path not in ALLOWED:
        raise HTTPException(status_code=404, detail="Source file not available")
    real_path = (ROOT / path).resolve()
    if not real_path.is_relative_to(ROOT) or not real_path.is_file():
        raise HTTPException(status_code=404, detail="Source file not available")
    return {"path": path, "content": real_path.read_text(encoding="utf-8")}


if __name__ == "__main__":
    run(
        app, frontend="frontend", port=int(os.getenv("PORT", "1111")),
        host="0.0.0.0" if "--prod" in sys.argv else "127.0.0.1",
        trace=False,
    )

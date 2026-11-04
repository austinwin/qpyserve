"""Real QPyServe app. Only allowlisted source files are displayed publicly."""
from datetime import datetime, timezone
from pathlib import Path
import os, time, sys
from math import pi
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from qpyserve import run

ROOT = Path(__file__).resolve().parent
STARTED = time.monotonic()
app = FastAPI(title="QPyServe Live Showcase", version="1.0.0")

SOURCE_FILES = {
    "backend": ["main.py"],
    "frontend": ["frontend/src/App.jsx", "frontend/src/main.jsx", "frontend/src/index.css", "frontend/vite.config.js", "frontend/package.json"],
    "deployment": ["Dockerfile", "requirements.txt"],
}
ALLOWED = {path for group in SOURCE_FILES.values() for path in group}

class FlowInput(BaseModel):
    flow_gpm: float = Field(ge=0, le=200000)
    diameter_in: float = Field(gt=0, le=144)

@app.get("/api/health")
def health():
    return {"status": "ok", "framework": "QPyServe + FastAPI",
            "uptime_seconds": round(time.monotonic() - STARTED, 1),
            "server_time": datetime.now(timezone.utc).isoformat()}

@app.post("/api/flow")
def calculate_flow(body: FlowInput):
    """Instructional velocity calculation, not a hydraulic design model."""
    area_sqft = pi * (body.diameter_in / 12) ** 2 / 4
    flow_cfs = body.flow_gpm / 448.831
    return {"velocity_fps": round(flow_cfs / area_sqft, 3),
            "flow_mgd": round(body.flow_gpm * 1440 / 1_000_000, 3),
            "area_sqft": round(area_sqft, 4),
            "flow_gpm": body.flow_gpm, "diameter_in": body.diameter_in,
            "formula": "velocity = (GPM / 448.831) / (pi * (diameter_in / 12)^2 / 4)"}

@app.get("/api/source-files")
def source_files():
    return {group: [{"id": path, "name": path.split("/")[-1]} for path in paths]
            for group, paths in SOURCE_FILES.items()}

@app.get("/api/source")
def source(path: str):
    if path not in ALLOWED:
        raise HTTPException(status_code=404, detail="Source file not available")
    resolved = (ROOT / path).resolve()
    if not resolved.is_relative_to(ROOT) or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Source file not available")
    return {"path": path, "content": resolved.read_text(encoding="utf-8")}

if __name__ == "__main__":
    run(app, frontend="frontend", port=int(os.getenv("PORT", "1111")),
        host="0.0.0.0" if "--prod" in sys.argv else "127.0.0.1", trace=False)

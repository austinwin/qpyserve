"""Node-free QPyServe Data Bridge dashboard starter (public sample data only)."""
from pathlib import Path

from fastapi import FastAPI
from qpyserve import run
from qpyserve.data import DataBridge

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="QPyServe Dashboard Starter")

# Demonstration data is PUBLIC. Add FastAPI authorization dependencies before
# connecting private, sensitive, or tenant-specific datasets in production.
DataBridge(app, public=True, sources={"records": ROOT / "data" / "sample.csv"})

if __name__ == "__main__":
    run(app, frontend=str(ROOT / "frontend"), port=1111)

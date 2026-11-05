"""Minimal, auto-refreshing dashboard with one CSV data source.

Run from this directory: python main.py
Requires: pip install -e ".[data]" in the QPyServe repo root.
"""
from fastapi import FastAPI
from qpyserve import run
from qpyserve.data import DataBridge

app = FastAPI()
DataBridge(app, public=True, sources={"pumpage": "data/pumpage.csv"})

if __name__ == "__main__":
    run(app, frontend="frontend", port=1111)

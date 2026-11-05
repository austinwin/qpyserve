"""One million lazy readings with an ordinary HTML frontend. Run: python main.py."""
from fastapi import FastAPI
from qpyserve import run
from qpyserve.data import DataBridge

app = FastAPI(title="QPyServe Data Bridge demo")
bridge = DataBridge(app, public=True)
bridge.relation(
    "readings",
    lambda con, request: con.sql(
        "SELECT i::BIGINT AS id, "
        "('Sensor ' || CAST(i % 1000 AS VARCHAR)) AS sensor, "
        "CAST((i % 400) / 10.0 + 30 AS DOUBLE) AS pressure_psi, "
        "CASE WHEN i % 5 = 0 THEN 'Alert' ELSE 'Normal' END AS status "
        "FROM range(1000000) AS t(i)"
    ),
    description="One million synthetic records, computed lazily in DuckDB",
)

if __name__ == "__main__":
    run(app, frontend="frontend", port=1111)

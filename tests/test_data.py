"""Real DuckDB + Arrow integration checks for the opt-in QPyServe Data Bridge."""
from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
import pytest

pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")

from qpyserve._data import DataBridge


def _app(*, max_limit: int = 10_000):
    app = FastAPI()
    bridge = DataBridge(app, public=True, max_limit=max_limit)
    # DuckDB generates rows lazily; does not materialize this million-row relation.
    bridge.relation(
        "sensors",
        lambda con, req: con.sql(
            "SELECT i::INTEGER AS sensor_id, (i % 100)::INTEGER AS pressure, "
            "CASE WHEN i % 2 = 0 THEN 'north' ELSE 'south' END AS zone "
            "FROM range(1000000) AS t(i)"
        ),
        description="One million synthetic readings",
    )
    return TestClient(app), bridge


def test_security_requires_explicit_public_or_dependencies():
    with pytest.raises(ValueError, match="protected"):
        DataBridge(FastAPI())


def test_schema_does_not_fetch_entire_dataset():
    client, _ = _app()
    response = client.get("/api/data/sensors")
    assert response.status_code == 200
    schema = response.json()
    assert schema["name"] == "sensors"
    assert schema["max_limit"] == 10_000
    assert [column["name"] for column in schema["columns"]] == [
        "sensor_id", "pressure", "zone"
    ]
    assert "arrow" in schema["formats"]
    assert "no-store" in response.headers["cache-control"]


def test_server_side_projection_filter_sort_and_pagination():
    client, _ = _app()
    q = {
        "columns": ["sensor_id", "zone"],
        "filters": [
            {"column": "pressure", "op": "gte", "value": 98},
            {"column": "zone", "op": "eq", "value": "north"},
        ],
        "sort": [{"column": "sensor_id", "desc": True}],
        "limit": 3,
        "offset": 1,
    }
    response = client.post("/api/data/sensors/query", json=q)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result == {
        "rows": [
            {"sensor_id": 999898, "zone": "north"},
            {"sensor_id": 999798, "zone": "north"},
            {"sensor_id": 999698, "zone": "north"},
        ],
        "limit": 3,
        "offset": 1,
        "has_more": True,
    }


def test_literal_string_cannot_inject_sql():
    app = FastAPI()
    bridge = DataBridge(app, public=True)
    bridge.relation(
        "names",
        lambda con, req: con.sql(
            "SELECT * FROM (VALUES (1, 'safe'), (2, 'x'' OR 1=1 --')) AS t(id, name)"
        ),
    )
    client = TestClient(app)
    payload = {
        "filters": [{"column": "name", "op": "eq", "value": "x' OR 1=1 --"}],
        "limit": 10,
    }
    response = client.post("/api/data/names/query", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["rows"] == [{"id": 2, "name": "x' OR 1=1 --"}]


@pytest.mark.parametrize("payload", [
    {"limit": 10001},
    {"limit": 0},
    {"columns": ["private"]},
    {"columns": []},
    {"filters": [{"column": "sensor_id; DROP TABLE x", "op": "eq", "value": 1}]},
    {"sort": [{"column": "sensor_id DESC; DELETE", "desc": True}]},
    {"filters": [{"column": "sensor_id", "op": "in", "value": [1] * 101}]},
    {"filters": [{"column": "sensor_id", "op": "eq", "value": {"$gt": 0}}]},
    {"offset": 1000001},
    {"raw_sql": "SELECT * FROM sensors"},
])
def test_invalid_query_is_rejected(payload):
    client, _ = _app()
    response = client.post("/api/data/sensors/query", json=payload)
    assert response.status_code == 422, response.text


def test_arrow_ipc_stream_round_trip():
    import pyarrow as pa

    client, _ = _app()
    payload = {
        "columns": ["sensor_id", "pressure"],
        "filters": [{"column": "sensor_id", "op": "gte", "value": 999_995}],
        "sort": [{"column": "sensor_id"}],
        "limit": 3,
    }
    response = client.post("/api/data/sensors/query?format=arrow", json=payload)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/vnd.apache.arrow.stream")
    table = pa.ipc.open_stream(pa.py_buffer(response.content)).read_all()
    assert table.to_pylist() == [
        {"sensor_id": 999995, "pressure": 95},
        {"sensor_id": 999996, "pressure": 96},
        {"sensor_id": 999997, "pressure": 97},
    ]


def test_arrow_zero_rows_is_valid_stream():
    import pyarrow as pa

    client, _ = _app()
    payload = {
        "columns": ["sensor_id", "pressure"],
        "filters": [{"column": "sensor_id", "op": "eq", "value": -1}],
        "limit": 10,
    }
    response = client.post("/api/data/sensors/query?format=arrow", json=payload)
    assert response.status_code == 200, response.text
    table = pa.ipc.open_stream(pa.py_buffer(response.content)).read_all()
    assert table.num_rows == 0
    assert table.column_names == ["sensor_id", "pressure"]


def test_nonexistent_and_duplicate_datasets():
    client, bridge = _app()
    assert client.get("/api/data/nonexistent").status_code == 404
    assert client.post("/api/data/nonexistent/query", json={}).status_code == 404
    with pytest.raises(ValueError, match="already registered"):
        bridge.relation("sensors", lambda conn, req: conn.sql("SELECT 1"))
    with pytest.raises(ValueError, match="Dataset names"):
        bridge.relation("../secret", lambda conn, req: conn.sql("SELECT 1"))


def test_route_authorization_and_tenant_scope():
    def authorize(x_token: str | None = Header(default=None)):
        if x_token not in ("north", "south"):
            raise HTTPException(status_code=403, detail="Forbidden")

    app = FastAPI()
    bridge = DataBridge(app, dependencies=[Depends(authorize)])
    bridge.relation(
        "private",
        lambda con, request: con.sql(
            "SELECT id FROM range(5) t(id) WHERE id % 2 = "
            + ("0" if request.headers.get("x-token") == "north" else "1")
        ),
    )
    client = TestClient(app)
    assert client.get("/api/data/private").status_code == 403
    assert client.post("/api/data/private/query", json={}).status_code == 403
    ok = client.post(
        "/api/data/private/query", json={"limit": 10}, headers={"X-Token": "north"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["rows"] == [{"id": 0}, {"id": 2}, {"id": 4}]
    assert "no-store" in ok.headers["cache-control"]


def test_js_module_is_same_origin():
    client, _ = _app()
    r = client.get("/api/data/_client.js")
    assert r.status_code == 200
    assert "export function dataset" in r.text
    assert "no-store" in r.headers["cache-control"]


def test_simple_csv_source_and_file_refresh(tmp_path):
    csv = tmp_path / "pumpage.csv"
    csv.write_text("day,mgd\n1,20\n2,30\n", encoding="utf-8")
    app = FastAPI()
    DataBridge(app, public=True, sources={"pumpage": csv})
    client = TestClient(app)

    schema = client.get("/api/data/pumpage")
    assert schema.status_code == 200, schema.text
    assert [x["name"] for x in schema.json()["columns"]] == ["day", "mgd"]
    first = client.get("/api/data/pumpage/version")
    assert first.status_code == 200
    first_version = first.json()["version"]
    assert isinstance(first_version, str) and len(first_version) == 24
    assert str(tmp_path) not in first.text
    assert "no-store" in first.headers["cache-control"]

    query = client.post(
        "/api/data/pumpage/query",
        json={"columns": ["day", "mgd"], "limit": 2, "sort": [{"column": "day"}]},
    )
    assert query.status_code == 200, query.text
    assert query.json()["rows"] == [{"day": 1, "mgd": 20}, {"day": 2, "mgd": 30}]

    # Changing the file should not require restarting FastAPI or resetting cache.
    csv.write_text("day,mgd\n1,20\n2,30\n3,100\n", encoding="utf-8")
    second = client.get("/api/data/pumpage/version")
    assert second.status_code == 200
    assert second.json()["version"] != first_version
    rows = client.post(
        "/api/data/pumpage/query", json={"sort": [{"column": "day"}], "limit": 3}
    ).json()["rows"]
    assert rows[-1] == {"day": 3, "mgd": 100}

    csv.unlink()
    missing = client.get("/api/data/pumpage/version")
    assert missing.status_code == 503
    assert str(tmp_path) not in missing.text


def test_simple_parquet_source(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / "pipes.parquet"
    pq.write_table(
        pa.table({"pipe_id": [1, 2, 3], "diameter": [6, 12, 24]}), path
    )
    app = FastAPI()
    bridge = DataBridge(app, public=True, sources={"pipes": path})
    client = TestClient(app)
    page = client.post(
        "/api/data/pipes/query",
        json={
            "columns": ["pipe_id", "diameter"],
            "filters": [{"column": "diameter", "op": "gte", "value": 12}],
            "limit": 10,
        },
    )
    assert page.status_code == 200, page.text
    assert page.json()["rows"] == [
        {"pipe_id": 2, "diameter": 12}, {"pipe_id": 3, "diameter": 24}
    ]
    assert client.get("/api/data/pipes/version").json()["version"] is not None
    bridge.source("second", path)
    assert client.get("/api/data/second/version").status_code == 200


def test_no_implicit_public_data_or_sql_paths(tmp_path):
    file = tmp_path / "secret.csv"
    file.write_text("id\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="protected"):
        DataBridge(FastAPI(), sources={"secret": file})
    with pytest.raises(ValueError, match="source must be"):
        DataBridge(FastAPI(), public=True, sources={"bad": "database.sqlite"})
    with pytest.raises(ValueError, match="Dataset names"):
        DataBridge(FastAPI(), public=True, sources={"../secret": file})


def test_version_endpoint_respects_fastapi_auth():
    def auth(x_token: str | None = Header(default=None)):
        if x_token != "allowed":
            raise HTTPException(status_code=403, detail="Forbidden")

    app = FastAPI()
    bridge = DataBridge(app, dependencies=[Depends(auth)])
    bridge.relation("dynamic", lambda con, req: con.sql("SELECT 1 AS id"))
    client = TestClient(app)
    assert client.get("/api/data/dynamic/version").status_code == 403
    response = client.get(
        "/api/data/dynamic/version", headers={"X-Token": "allowed"}
    )
    assert response.status_code == 200
    assert response.json() == {"version": None}


def test_dashboard_starter_uses_real_data_bridge(tmp_path, monkeypatch):
    import runpy
    from qpyserve._cli import create_project

    project = create_project(tmp_path / "dashboard", template="dashboard")
    module = runpy.run_path(str(project / "main.py"), run_name="dashboard_test")
    client = TestClient(module["app"])
    response = client.post(
        "/api/data/records/query",
        json={"columns": ["Date", "Revenue"], "limit": 30},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["rows"]) == 12
    assert response.json()["rows"][-1]["Revenue"] == 10320
    assert client.get("/api/data/records/version").status_code == 200


def test_data_watch_demo_is_runnable_and_returns_expected_csv(tmp_path, monkeypatch):
    import runpy
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "examples" / "data-watch"
    monkeypatch.chdir(root)
    module = runpy.run_path(str(root / "main.py"), run_name="data_watch_test")
    app = module["app"]
    client = TestClient(app)
    response = client.post(
        "/api/data/pumpage/query",
        json={"columns": ["Date", "TotalWP"], "sort": [{"column": "Date"}], "limit": 10},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert len(rows) == 6
    assert rows[0]["Date"] == "2026-10-30"
    assert rows[-1]["TotalWP"] == 368.6
    assert client.get("/api/data/pumpage/version").status_code == 200

"""Database source contract tests: real SQL execution and cross-dialect compilation."""
from __future__ import annotations

from datetime import datetime
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
import pytest

sa = pytest.importorskip("sqlalchemy")

from qpyserve.data import DataBridge, db


@pytest.fixture()
def database(tmp_path, monkeypatch):
    path = tmp_path / "pumpage.sqlite"
    url = f"sqlite:///{path.as_posix()}"
    monkeypatch.setenv("TEST_DB_URL", url)
    engine = sa.create_engine(url)
    metadata = sa.MetaData()
    table = sa.Table(
        "DailyPumpage",
        metadata,
        sa.Column("Day", sa.Integer, primary_key=True),
        sa.Column("TotalWP", sa.Float),
        sa.Column("Status", sa.String(50)),
        sa.Column("UpdatedAt", sa.DateTime),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                {"Day": i, "TotalWP": float(i) + 0.5,
                 "Status": "ok" if i % 2 == 0 else "bad",
                 "UpdatedAt": datetime(2026, 11, 1)}
                for i in range(1000)
            ],
        )
    yield url, table, engine
    engine.dispose()


def test_one_line_database_registration(database):
    app = FastAPI()
    DataBridge(
        app,
        public=True,
        max_limit=50,
        sources={"pumpage": db("DailyPumpage", url_env="TEST_DB_URL", updated_at="UpdatedAt")},
    )
    client = TestClient(app)
    schema = client.get("/api/data/pumpage")
    assert schema.status_code == 200, schema.text
    assert {c["name"] for c in schema.json()["columns"]} == {
        "Day", "TotalWP", "Status", "UpdatedAt"
    }
    assert schema.json()["formats"] == ["json"]
    page = client.post("/api/data/pumpage/query", json={
        "columns": ["Day", "TotalWP"],
        "filters": [{"column": "TotalWP", "op": "gte", "value": 900.5}],
        "sort": [{"column": "Day", "desc": True}],
        "limit": 2,
        "offset": 1,
    })
    assert page.status_code == 200, page.text
    assert page.json() == {
        "rows": [{"Day": 998, "TotalWP": 998.5}, {"Day": 997, "TotalWP": 997.5}],
        "limit": 2,
        "offset": 1,
        "has_more": True,
    }
    status = client.get("/api/data/pumpage/version")
    assert status.status_code == 200, status.text
    assert status.json() == {"version": "2026-11-01 00:00:00"}
    assert "sqlite" not in status.text
    arrow = client.post("/api/data/pumpage/query?format=arrow", json={})
    assert arrow.status_code == 501
    assert "Arrow is not yet supported" in arrow.text


def test_database_version_detects_updates(database):
    _, table, engine = database
    app = FastAPI()
    DataBridge(app, public=True, sources={
        "pumpage": db("DailyPumpage", url_env="TEST_DB_URL", updated_at="UpdatedAt")
    })
    client = TestClient(app)
    before = client.get("/api/data/pumpage/version").json()["version"]
    with engine.begin() as conn:
        conn.execute(
            table.update().where(table.c.Day == 100).values(
                UpdatedAt=datetime(2026, 11, 2), TotalWP=5000.5
            )
        )
    after = client.get("/api/data/pumpage/version").json()["version"]
    assert after != before
    q = client.post("/api/data/pumpage/query", json={
        "filters": [{"column": "Day", "op": "eq", "value": 100}],
        "limit": 5,
    })
    assert q.status_code == 200
    assert q.json()["rows"][0]["TotalWP"] == 5000.5


@pytest.mark.parametrize("item", [
    {"columns": ["WRONG"]},
    {"filters": [{"column": "Status", "op": "eq", "value": "a' OR 1=1 --"}]},
    {"filters": [{"column": "Day", "op": "in", "value": [1] * 101}]},
    {"filters": [{"column": "Day", "op": "eq", "value": {"sql": "drop"}}]},
    {"filters": [{"column": "TotalWP", "op": "gt", "value": None}]},
    {"sort": [{"column": "Day; DROP TABLE DailyPumpage", "desc": True}]},
    {"limit": 51},
])
def test_database_validates_predicates_and_limits(database, item):
    app = FastAPI()
    DataBridge(app, public=True, max_limit=50, sources={
        "pumpage": db("DailyPumpage", url_env="TEST_DB_URL")
    })
    client = TestClient(app)
    resp = client.post("/api/data/pumpage/query", json=item)
    if item.get("filters", [{}])[0].get("value") == "a' OR 1=1 --":
        assert resp.status_code == 200
        assert resp.json()["rows"] == []
    else:
        assert resp.status_code == 422, resp.text


def test_database_filters_are_bound_parameters(database):
    from qpyserve._database import DatabaseReader

    reader = DatabaseReader(db("DailyPumpage", url_env="TEST_DB_URL"))
    from qpyserve._data import DataFilter, DataQuery

    query = reader._query(
        DataQuery(filters=[DataFilter(column="Status", op="eq", value="bad' OR 1=1 --")]),
        max_limit=10_000,
    )
    compiled = query.compile(reader.engine)
    assert "bad' OR 1=1 --" not in str(compiled)
    assert "bad' OR 1=1 --" in compiled.params.values()


def test_database_auth_is_required_and_metadata_protected(database):
    def authorize(x_token: str | None = Header(default=None)):
        if x_token != "secret":
            raise HTTPException(status_code=403, detail="Forbidden")

    app = FastAPI()
    DataBridge(
        app,
        dependencies=[Depends(authorize)],
        sources={"pumpage": db("DailyPumpage", url_env="TEST_DB_URL")},
    )
    client = TestClient(app)
    for path in ("/api/data/pumpage", "/api/data/pumpage/version"):
        assert client.get(path).status_code == 403
    assert client.post("/api/data/pumpage/query", json={}).status_code == 403
    assert client.get(
        "/api/data/pumpage", headers={"X-Token": "secret"}
    ).status_code == 200
    assert client.get("/api/data/_client.js").status_code == 200


def test_server_credential_does_not_leak(database, monkeypatch):
    monkeypatch.delenv("TEST_DB_URL")
    app = FastAPI()
    DataBridge(app, public=True, sources={
        "pumpage": db("DailyPumpage", url_env="TEST_DB_URL")
    })
    client = TestClient(app)
    for response in (
        client.get("/api/data/pumpage"),
        client.post("/api/data/pumpage/query", json={}),
        client.get("/api/data/pumpage/version"),
    ):
        assert response.status_code == 503, response.text
        assert "TEST_DB_URL" not in response.text
        assert "sqlalchemy" not in response.text.lower()


def test_database_source_configuration_rejects_arbitrary_sql():
    for bad in ("SELECT * FROM table", "dbo.table; DROP TABLE test", "a.b.c"):
        with pytest.raises(ValueError):
            db(bad)
    with pytest.raises(ValueError):
        db("GoodTable", schema="dbo; DROP TABLE X")
    with pytest.raises(ValueError, match="protected"):
        DataBridge(FastAPI(), sources={"pumpage": db("DailyPumpage")})


def test_sqlserver_query_compiles_with_order_by_and_offset(database):
    from sqlalchemy.dialects import mssql
    from qpyserve._data import DataQuery
    from qpyserve._database import DatabaseReader

    reader = DatabaseReader(db("DailyPumpage", url_env="TEST_DB_URL"))
    query = reader._query(DataQuery(limit=3, offset=5), 100)
    compiled = str(query.compile(dialect=mssql.dialect()))
    assert "ORDER BY" in compiled
    assert "ROW_NUMBER" in compiled or "OFFSET" in compiled
    assert "FETCH" in compiled or "ROW_NUMBER" in compiled


def test_database_source_without_update_column_has_null_version(database):
    app = FastAPI()
    DataBridge(app, public=True, sources={
        "pumpage": db("DailyPumpage", url_env="TEST_DB_URL")
    })
    assert TestClient(app).get("/api/data/pumpage/version").json() == {"version": None}

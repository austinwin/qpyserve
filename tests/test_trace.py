"""Regression tests for development-only request tracing and privacy."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.testclient import TestClient

from qpyserve._frontend import attach_frontend
from qpyserve._tooling import vite_config
from qpyserve._trace import TraceStore, install_trace


def traced_client() -> TestClient:
    app = FastAPI()

    @app.get("/api/items/{item_id}")
    def item(item_id: str):
        return {"id": item_id}

    @app.get("/api/failure")
    def failure():
        raise HTTPException(503, "PRIVATE_RESPONSE_MESSAGE")

    @app.get("/api/crash")
    def crash():
        raise RuntimeError("PRIVATE_EXCEPTION_MESSAGE")

    install_trace(app, ["/api", "/__qpyserve"])
    return TestClient(app, raise_server_exceptions=False)


def test_request_id_is_correlated_without_leaking_secrets():
    client = traced_client()
    result = client.get(
        "/api/items/USER-TOKEN-123?api_key=PRIVATE_QUERY",
        headers={"authorization": "Bearer PRIVATE_HEADER"},
    )
    assert result.status_code == 200
    request_id = result.headers["x-qpyserve-trace-id"]
    assert len(request_id) == 12
    report = client.get("/__qpyserve/trace").json()
    assert report["requests"][-1]["id"] == request_id
    assert report["requests"][-1]["route"] == "/api/items/{item_id}"
    assert report["requests"][-1]["status"] == 200
    for private in ("PRIVATE_QUERY", "PRIVATE_HEADER", "USER-TOKEN"):
        assert private not in str(report)


def test_api_failures_and_exceptions_without_messages():
    client = traced_client()
    assert client.get("/api/failure").status_code == 503
    assert client.get("/api/crash").status_code == 500
    report = client.get("/__qpyserve/trace").json()["requests"]
    assert [item["status"] for item in report] == [503, 500]
    assert report[-1]["exception"] == "RuntimeError"
    assert "PRIVATE_EXCEPTION_MESSAGE" not in str(report)
    assert "PRIVATE_RESPONSE_MESSAGE" not in str(report)


def test_trace_resources_are_local_and_unrecorded():
    client = traced_client()
    assert client.get("/__qpyserve/trace").json()["requests"] == []
    client_js = client.get("/__qpyserve/trace.js")
    assert client_js.status_code == 200
    assert "Copy AI report" in client_js.text
    assert client_js.headers["cache-control"] == "no-store"
    assert client_js.headers["x-content-type-options"] == "nosniff"
    assert client.get("/__qpyserve/trace").json()["requests"] == []


def test_html_injects_trace_only_in_dev(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>Hello</body></html>")
    app = FastAPI()
    install_trace(app, ["/api"])
    attach_frontend(app, tmp_path, live_reload=True, trace_enabled=True)
    assert "/__qpyserve/trace.js" in TestClient(app).get("/").text

    prod_app = FastAPI()
    attach_frontend(prod_app, tmp_path)
    client = TestClient(prod_app)
    assert "/__qpyserve/trace.js" not in client.get("/").text
    assert client.get("/__qpyserve/trace").status_code == 404


def test_vite_generated_config_injects_trace_and_preserves_user_plugins(tmp_path):
    (tmp_path / "vite.config.js").write_text("export default { plugins: [] };")
    config = vite_config(
        tmp_path, host="127.0.0.1", port=1111, backend_port=1112,
        trace_enabled=True,
    ).read_text()
    assert "qpyserve-trace" in config
    assert "transformIndexHtml" in config
    assert "vite.config.js" in config
    assert "/__qpyserve/trace.js" in config
    other = vite_config(
        tmp_path, host="127.0.0.1", port=1111, backend_port=1112,
        trace_enabled=False,
    ).read_text()
    assert "qpyserve-trace" not in other


def test_trace_store_is_bounded():
    store = TraceStore(limit=2)
    for i in range(8):
        store.record({"i": i})
    assert [item["i"] for item in store.snapshot()] == [6, 7]


def test_websocket_is_uninstrumented():
    app = FastAPI()

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        await socket.send_text("ok")
        await socket.close()

    install_trace(app, ["/api", "/ws"])
    client = TestClient(app)
    with client.websocket_connect("/ws") as socket:
        assert socket.receive_text() == "ok"
    assert client.get("/__qpyserve/trace").json()["requests"] == []

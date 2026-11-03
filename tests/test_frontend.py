from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from qpyserve._frontend import attach_frontend
from qpyserve._runtime import _has_vite, _vite_config


def client_with_site(tmp_path: Path, live_reload=False):
    (tmp_path / "index.html").write_text("<html><body>Hello</body></html>")
    (tmp_path / "app.js").write_text("console.log('ok')")
    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    attach_frontend(app, tmp_path, live_reload=live_reload)
    return TestClient(app)


def test_api_and_html_share_origin(tmp_path):
    client = client_with_site(tmp_path)
    assert client.get("/api/ping").json() == {"ok": True}
    assert "Hello" in client.get("/").text
    assert "console.log" in client.get("/app.js").text
    assert client.get("/__qpyserve/health").json() == {"status": "ok"}


def test_spa_history_fallback_and_missing_assets(tmp_path):
    client = client_with_site(tmp_path)
    assert "Hello" in client.get("/facilities/123", headers={"accept": "text/html"}).text
    assert client.get("/missing.js").status_code == 404
    assert client.get("/api/missing", headers={"accept": "text/html"}).status_code == 404
    assert client.post("/api/missing").status_code == 404
    assert client.get("/apiary", headers={"accept": "application/json"}).status_code == 404
    assert client.get("/../other.txt").status_code == 404


def test_html_live_reload_is_dev_only(tmp_path):
    dev = client_with_site(tmp_path, live_reload=True)
    assert "__qpyserve/version" in dev.get("/").text
    version = dev.get("/__qpyserve/version")
    assert version.status_code == 200 and version.json()["version"] > 0
    prod = client_with_site(tmp_path)
    assert "__qpyserve/version" not in prod.get("/").text
    assert prod.get("/__qpyserve/version").status_code == 404


def test_vite_detection_and_config(tmp_path):
    (tmp_path / "package.json").write_text('{"devDependencies":{"vite":"^6.0.0"}}')
    (tmp_path / "vite.config.ts").write_text("export default {}")
    assert _has_vite(tmp_path)
    generated = _vite_config(tmp_path, host="127.0.0.1", port=1111, backend_port=1112)
    text = generated.read_text()
    assert "vite.config.ts" in text
    assert "1112" in text
    assert "strictPort" in text


def test_missing_index(tmp_path):
    with pytest.raises(FileNotFoundError):
        attach_frontend(FastAPI(), tmp_path)


def test_custom_api_path_never_falls_back_to_html(tmp_path):
    (tmp_path / "index.html").write_text("<html>App</html>")
    app = FastAPI()

    @app.get("/ws/status")
    def status():
        return {"status": "ready"}

    attach_frontend(app, tmp_path, api_paths=["/ws", "/reports"])
    client = TestClient(app)
    assert client.get("/ws/status").json() == {"status": "ready"}
    assert client.get("/ws/missing", headers={"accept": "text/html"}).status_code == 404
    assert client.get("/reports/missing", headers={"accept": "text/html"}).status_code == 404
    assert "App" in client.get("/my-page", headers={"accept": "text/html"}).text


def test_version_scan_is_cached_for_multiple_clients(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>Test</html>")
    app = FastAPI()
    from qpyserve import _frontend
    scans = []
    monkeypatch.setattr(_frontend, "_version", lambda _: scans.append(1) or 42)
    attach_frontend(app, tmp_path, live_reload=True)
    client = TestClient(app)
    assert client.get("/__qpyserve/version").json()["version"] == 42
    assert client.get("/__qpyserve/version").json()["version"] == 42
    assert scans == [1]


def test_hidden_and_project_source_files_not_public(tmp_path):
    client = client_with_site(tmp_path)
    for name in (".env", "package.json", "vite.config.js", "app.py", "node_modules/secret.js"):
        candidate = tmp_path / name
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("SECRET")
        assert client.get("/" + name).status_code == 404
    assert client.get("/").headers["cache-control"] == "no-cache"

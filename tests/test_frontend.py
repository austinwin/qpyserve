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

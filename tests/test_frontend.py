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


def test_symlink_to_hidden_file_is_not_exposed(tmp_path):
    client = client_with_site(tmp_path)
    secret = tmp_path / ".env"
    secret.write_text("TOKEN=secret")
    alias = tmp_path / "public.txt"
    try:
        alias.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable")
    assert client.get("/public.txt").status_code == 404


def test_directory_index_symlink_escape_is_blocked(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html>Home</html>")
    outside = tmp_path / "private.html"
    outside.write_text("PRIVATE")
    child = site / "subdir"
    child.mkdir()
    try:
        (child / "index.html").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable")
    client = TestClient(attach_frontend(FastAPI(), site))
    assert client.get("/subdir/").status_code == 404
    assert "PRIVATE" not in client.get("/subdir/").text


def test_entrypoint_symlink_to_outside_is_rejected(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    secret = tmp_path / "secret.html"
    secret.write_text("SECRET")
    try:
        (site / "index.html").symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(ValueError, match="index.html"):
        attach_frontend(FastAPI(), site)


def test_plain_frontend_blocks_private_key_files(tmp_path):
    client = client_with_site(tmp_path)
    for name in ("private.pem", "client.key", "credentials.json", "id_ed25519", "data.sqlite"):
        (tmp_path / name).write_text("PRIVATE")
        assert client.get("/" + name).status_code == 404


def test_vite_fingerprinted_assets_are_immutable_in_production(tmp_path):
    (tmp_path / "index.html").write_text("<html>App</html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-B3x7kmP2.js").write_text("console.log('app')")
    (assets / "index.js").write_text("console.log('plain')")
    app = attach_frontend(FastAPI(), tmp_path, built_vite=True)
    client = TestClient(app)
    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/assets/index-B3x7kmP2.js").headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "immutable" not in client.get("/assets/index.js").headers.get("cache-control", "")
    dev = TestClient(attach_frontend(FastAPI(), tmp_path, live_reload=True, built_vite=True))
    assert dev.get("/assets/index-B3x7kmP2.js").headers["cache-control"] == "no-store"

def test_only_public_asset_types_are_exposed(tmp_path):
    client = client_with_site(tmp_path)
    for name in ("settings.yaml", "config.toml", "Dockerfile", "run.sh", "bundle.map"):
        (tmp_path / name).write_text("INTERNAL")
        assert client.get("/" + name).status_code == 404
    for name in ("map.geojson", "map.pbf", "data.csv", "style.css", "app.wasm"):
        (tmp_path / name).write_text("PUBLIC")
        assert client.get("/" + name).status_code == 200


def test_static_security_headers_do_not_change_api(tmp_path):
    client = client_with_site(tmp_path)
    for path in ("/", "/app.js"):
        assert client.get(path).headers["x-content-type-options"] == "nosniff"
    assert "x-content-type-options" not in client.get("/api/ping").headers


def test_symlink_to_allowed_file_outside_site_is_denied(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html>safe</html>")
    outside = tmp_path / "outside.txt"
    outside.write_text("PRIVATE")
    try:
        (site / "alias.txt").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    client = TestClient(attach_frontend(FastAPI(), site))
    assert client.get("/alias.txt").status_code == 404


def test_static_files_support_head_without_body(tmp_path):
    client = client_with_site(tmp_path)
    response = client.head("/app.js")
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["x-content-type-options"] == "nosniff"

"""Exercise every documented Trace 0.4 demo API failure."""

from pathlib import Path
import runpy

from fastapi.testclient import TestClient


def test_demo_routes():
    source = Path(__file__).resolve().parents[1] / "examples/trace-demo/main.py"
    app = runpy.run_path(str(source), run_name="example_import")["app"]
    client = TestClient(app, raise_server_exceptions=False)

    assert client.get("/api/hello").json()["message"] == "Hello from FastAPI"
    assert client.get("/api/failure").status_code == 503
    assert client.get("/api/rate-limit").status_code == 429
    assert client.get("/api/crash").status_code == 500

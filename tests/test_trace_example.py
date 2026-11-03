"""Exercise the documented Trace demonstration API."""

from pathlib import Path
import runpy

from fastapi.testclient import TestClient


def test_demo_routes():
    file = Path(__file__).resolve().parents[1] / "examples/trace-demo/main.py"
    app = runpy.run_path(str(file), run_name="example_import")["app"]
    client = TestClient(app)
    assert client.get("/api/hello").status_code == 200
    assert client.get("/api/failure").status_code == 503

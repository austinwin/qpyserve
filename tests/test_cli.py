"""Project generation and machine-readable diagnostics tests."""

from __future__ import annotations

import json
from pathlib import Path
import runpy

from fastapi.testclient import TestClient
import pytest

from qpyserve._cli import _copy_template, create_project, inspect_project, main


@pytest.mark.parametrize("template", ["html", "react", "vue"])
def test_new_project_has_working_fastapi_and_frontend(tmp_path: Path, template: str) -> None:
    project = create_project(tmp_path / "new-app", template=template)
    assert (project / "main.py").is_file()
    assert (project / "README.md").is_file()
    assert (project / "AGENTS.md").is_file()
    assert (project / "frontend" / "index.html").is_file()
    if template != "html":
        manifest = json.loads((project / "frontend" / "package.json").read_text())
        assert "vite" in manifest["devDependencies"]
        assert (project / "frontend" / "vite.config.js").is_file()
    else:
        assert not (project / "frontend" / "package.json").exists()

    # Import without executing the `if __name__ == '__main__'` runner.
    module = runpy.run_path(str(project / "main.py"), run_name="qpyserve_generated_test")
    response = TestClient(module["app"]).get("/api/hello")
    assert response.status_code == 200
    assert response.json()["message"] == "Hello from Python!"
    assert response.json()["time"]


def test_new_never_overwrites_an_existing_project(tmp_path: Path) -> None:
    project = create_project(tmp_path / "existing")
    marker = project / "main.py"
    marker.write_text("CUSTOM PROJECT")
    with pytest.raises(FileExistsError):
        create_project(project, template="react")
    assert marker.read_text() == "CUSTOM PROJECT"


def test_new_requires_existing_parent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Parent"):
        create_project(tmp_path / "missing" / "app")


def test_html_doctor_is_ready_without_node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = create_project(tmp_path / "plain")
    monkeypatch.setattr("qpyserve._cli.shutil.which", lambda _name: None)
    result = inspect_project(project)
    assert result["ready"] is True
    assert result["frontend"] == "html"
    assert not any(c["status"] == "error" for c in result["checks"])


def test_doctor_json_for_ai_agents(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = create_project(tmp_path / "plain")
    assert main(["doctor", str(project), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] is True
    assert report["frontend"] == "html"
    assert report["checks"]


def test_vite_doctor_reports_missing_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = create_project(tmp_path / "react", template="react")
    monkeypatch.setattr("qpyserve._cli.shutil.which", lambda _name: None)
    result = inspect_project(project)
    assert result["ready"] is False
    assert any(c["name"] == "JS runtime" for c in result["checks"])


def test_cli_create_defaults_to_html(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    destination = tmp_path / "starter"
    assert main(["new", str(destination)]) == 0
    assert "Created html + FastAPI project" in capsys.readouterr().out
    assert (destination / "frontend" / "index.html").is_file()


def test_cli_new_rejects_duplicate_destination(tmp_path: Path) -> None:
    target = tmp_path / "starter"
    target.mkdir()
    with pytest.raises(SystemExit) as result:
        main(["new", str(target)])
    assert result.value.code == 1


def test_doctor_reports_missing_project(tmp_path: Path) -> None:
    result = inspect_project(tmp_path / "missing")
    assert result["ready"] is False
    assert any(item["status"] == "error" for item in result["checks"])


def test_starters_are_packaged_as_resources() -> None:
    from importlib.resources import files

    root = files("qpyserve").joinpath("_starters")
    for template in ("html", "react", "vue", "dashboard"):
        assert root.joinpath(template, "frontend", "index.html").is_file()
    assert root.joinpath("dashboard", "data", "sample.csv").is_file()


def test_dashboard_starter_is_node_free_and_packaged(tmp_path: Path) -> None:
    project = create_project(tmp_path / "dashboard", template="dashboard")
    assert (project / "data" / "sample.csv").is_file()
    assert (project / "frontend" / "index.html").is_file()
    assert "DataBridge" in (project / "main.py").read_text()
    assert inspect_project(project)["frontend"] == "html"
    assert not (project / "frontend" / "package.json").exists()


def test_dashboard_csv_requires_explicit_public_consent(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_text("Date,Value\n2026-11-01,12\n", encoding="utf-8")
    target = tmp_path / "custom"
    with pytest.raises(ValueError, match="--public-data"):
        create_project(target, template="dashboard", data_source=source)
    assert not target.exists()
    project = create_project(target, template="dashboard", data_source=source, public_data=True)
    assert (project / "data" / "sample.csv").read_text() == source.read_text()


def test_dashboard_rejects_invalid_custom_files_before_creation(tmp_path: Path) -> None:
    source = tmp_path / "secret.txt"
    source.write_text("secret", encoding="utf-8")
    target = tmp_path / "custom"
    with pytest.raises(ValueError, match="existing CSV"):
        create_project(target, template="dashboard", data_source=source, public_data=True)
    assert not target.exists()
    with pytest.raises(ValueError, match="dashboard template"):
        create_project(target, template="react", data_source=source, public_data=True)
    assert not target.exists()


def test_dashboard_cli_flags(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "dashboard"
    assert main(["new", str(target), "--template", "dashboard"]) == 0
    output = capsys.readouterr().out
    assert "public" in output.lower()
    assert "qpyserve[data]" in output


def test_template_overlay_ignores_packaged_python_caches(tmp_path: Path) -> None:
    """A wheel may contain __pycache__ in common and the selected template."""
    common = tmp_path / "common"
    dashboard = tmp_path / "dashboard-source"
    destination = tmp_path / "result"
    for source in (common, dashboard):
        (source / "__pycache__").mkdir(parents=True)
        (source / "__pycache__" / "module.cpython-312.pyc").write_bytes(b"cache")
        (source / "frontend").mkdir()
    (common / "frontend" / "shared.txt").write_text("shared")
    (dashboard / "frontend" / "index.html").write_text("dashboard")
    (dashboard / "main.py").write_text("app")
    destination.mkdir()

    _copy_template(common, destination)
    _copy_template(dashboard, destination)

    assert (destination / "frontend" / "shared.txt").read_text() == "shared"
    assert (destination / "frontend" / "index.html").read_text() == "dashboard"
    assert (destination / "main.py").read_text() == "app"
    assert not (destination / "__pycache__").exists()

import sys

from fastapi import FastAPI
import pytest

from qpyserve import run


def test_run_validates_app(tmp_path):
    with pytest.raises(TypeError):
        run(object(), frontend=tmp_path)


def test_run_rejects_bad_port(tmp_path):
    with pytest.raises(ValueError, match="port"):
        run(FastAPI(), frontend=tmp_path, port=0)


def test_run_rejects_multiple_dev_workers(tmp_path):
    with pytest.raises(ValueError, match="workers"):
        run(FastAPI(), frontend=tmp_path, workers=2, mode="development")


def test_run_rejects_missing_frontend(tmp_path):
    with pytest.raises(FileNotFoundError, match="Frontend directory"):
        run(FastAPI(), frontend=tmp_path / "missing", mode="production")


def test_build_only_does_not_start_server(tmp_path, monkeypatch):
    import qpyserve._runtime as rt

    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"devDependencies":{"vite":"^6"}}')
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "main.py"), "--build"])
    calls = []
    monkeypatch.setattr(rt, "build_frontend", lambda _: calls.append("build"))
    monkeypatch.setattr(rt.uvicorn, "run", lambda *_a, **_kw: calls.append("serve"))
    run(FastAPI(), frontend=frontend)
    assert calls == ["build"]


def test_production_missing_build_explains_one_command_option(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"devDependencies":{"vite":"^6"}}')
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "main.py")])
    with pytest.raises(FileNotFoundError, match="--prod --build"):
        run(FastAPI(), frontend=frontend, mode="production")

def test_development_does_not_expose_vite_on_network(tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        run(FastAPI(), frontend=tmp_path, host="0.0.0.0")


def test_vite_build_dir_cannot_escape_frontend(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"devDependencies":{"vite":"^6"}}')
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "main.py")])
    with pytest.raises(ValueError, match="dist must"):
        run(FastAPI(), frontend=frontend, dist="../private")

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

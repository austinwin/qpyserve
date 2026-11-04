"""Importable Uvicorn factory so reload and multi-worker modes work."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

from fastapi import FastAPI

from ._frontend import attach_frontend
from ._trace import install_trace


def create_app() -> FastAPI:
    raw = os.environ.get("QPYSERVE_RUNTIME_CONFIG")
    if not raw:
        raise RuntimeError("qpyserve must be started through run(app, frontend=...).")
    config = json.loads(raw)
    module_name, separator, attribute = config["app_import"].partition(":")
    if not separator:
        raise ValueError("app_import must be in 'module:variable' format")
    module = importlib.import_module(module_name)
    app = module
    for part in attribute.split("."):
        app = getattr(app, part)
    if not isinstance(app, FastAPI):
        raise TypeError(f"{config['app_import']} does not resolve to a FastAPI app")
    if config.get("client_output"):
        from ._client import client_output, generate_client, save_client
        root = Path(config["project_dir"])
        destination = client_output(root, config["client_output"])
        report = save_client(generate_client(app.openapi()), destination)
        if report["skipped"]:
            print(
                f"[qpyserve] API generation skipped {len(report['skipped'])} "
                "unsupported operations",
                flush=True,
            )
    if config.get("trace", False):
        install_trace(app, config.get("api_paths", ("/api",)),
                      project_root=config.get("project_dir", "."))
    if config["serve_frontend"]:
        attach_frontend(app, config["static_directory"], live_reload=config["live_reload"],
                        api_paths=config.get("api_paths"),
                        built_vite=config.get("built_vite", False),
                        trace_enabled=config.get("trace", False))
    else:
        @app.get("/__qpyserve/health", include_in_schema=False)
        def qpyserve_health() -> dict[str, str]:
            return {"status": "ok"}
    return app

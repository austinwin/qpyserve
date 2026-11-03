"""Run a real FastAPI application with any HTML or Vite-based frontend."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Iterable, Literal

from fastapi import FastAPI
import uvicorn

from ._tooling import (
    build_frontend, ensure_dependencies, has_vite, normalize_api_paths,
    package_manager, vite_command, vite_config,
)

Mode = Literal["development", "production"]

# Retain private aliases for older users/tests; these are not public API.
_has_vite = has_vite
_vite_config = vite_config


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        # npm/pnpm/yarn/bun may create child processes on Windows.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        import contextlib
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run(
    app: FastAPI,
    frontend: str | Path = "frontend",
    port: int = 1111,
    *,
    host: str = "127.0.0.1",
    mode: Mode | None = None,
    app_import: str | None = None,
    dist: str = "dist",
    workers: int = 1,
    api_paths: Iterable[str] | None = None,
    build: bool | None = None,
) -> None:
    """One-command runner. `--build` builds and exits; `--prod --build` builds then serves.

    Plain HTML requires Python only. React/Vue require a Vite project and its selected
    JS package manager, installed automatically when frontend packages are missing.
    """
    if not isinstance(app, FastAPI):
        raise TypeError("run() requires a FastAPI application")
    if not 1 <= port <= 65535:
        raise ValueError("port must be 1..65535")
    if workers < 1:
        raise ValueError("workers must be >= 1")
    if mode is None:
        mode = "production" if "--prod" in sys.argv[1:] else os.environ.get("QPYSERVE_MODE", "development")
    if mode not in ("development", "production"):
        raise ValueError("mode must be 'development' or 'production'")
    if mode == "development" and host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            "The Vite development server must use a loopback host. "
            "Build the frontend and use production mode to serve remote users."
        )
    if mode == "development" and workers > 1:
        raise ValueError("Multiple workers are supported only in production")
    if build is None:
        build = "--build" in sys.argv[1:]
    paths = normalize_api_paths(api_paths)

    script = Path(sys.argv[0]).resolve()
    project_dir = script.parent
    root = Path(frontend)
    if not root.is_absolute():
        root = project_dir / root
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Frontend directory not found: {root}")
    if not dist or Path(dist).is_absolute() or ".." in Path(dist).parts:
        raise ValueError("dist must be a relative frontend build directory")

    vite = has_vite(root)
    static_directory = root / dist if vite else root
    if vite and not static_directory.resolve().is_relative_to(root):
        raise ValueError("dist must resolve inside the frontend directory")
    if build:
        if vite:
            build_frontend(root)
        else:
            print("[qpyserve] Plain HTML requires no build", flush=True)
        if mode != "production":
            return
    if mode == "production" and not (static_directory / "index.html").is_file():
        raise FileNotFoundError(
            f"Built frontend missing: {static_directory / 'index.html'}. "
            "Use 'python main.py --prod --build' to build and launch, "
            "or build once in CI and run 'python main.py --prod'."
        )
    if not vite and not (root / "index.html").is_file():
        raise FileNotFoundError(f"Plain HTML frontend must contain {root / 'index.html'}")
    if vite and mode == "development" and port == 65535:
        raise ValueError("Vite dev requires port and port+1; choose port <= 65534")

    if app_import is None:
        main_globals = vars(sys.modules["__main__"])
        app_var = next((k for k, v in main_globals.items() if v is app and k.isidentifier()), None)
        if not app_var or not script.stem.isidentifier():
            raise ValueError("Cannot locate FastAPI app. Pass app_import='main:app' explicitly.")
        app_import = f"{script.stem}:{app_var}"

    config = {
        "app_import": app_import,
        "serve_frontend": not (vite and mode == "development"),
        "static_directory": str(static_directory),
        "live_reload": not vite and mode == "development",
        "api_paths": paths,
        "built_vite": vite and mode == "production",
    }
    previous = os.environ.get("QPYSERVE_RUNTIME_CONFIG")
    os.environ["QPYSERVE_RUNTIME_CONFIG"] = json.dumps(config)
    vite_process: subprocess.Popen | None = None
    generated_config: Path | None = None
    try:
        if vite and mode == "development":
            manager = package_manager(root)
            command = ensure_dependencies(root, manager)
            generated_config = vite_config(root, host=host, port=port,
                                           backend_port=port + 1, api_paths=paths)
            cmd = vite_command(command, manager, "--config", generated_config.name)
            kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                      if os.name == "nt" else {"start_new_session": True})
            vite_process = subprocess.Popen(cmd, cwd=root, **kwargs)
            print(f"[qpyserve] http://localhost:{port} (Vite) /api -> localhost:{port + 1}", flush=True)
            uvicorn.run("qpyserve._entry:create_app", factory=True, host="127.0.0.1",
                        port=port + 1, reload=True, reload_dirs=[str(project_dir)],
                        reload_includes=["*.py"],
                        reload_excludes=["node_modules", "dist", ".qpyserve.vite.config.mjs"])
        else:
            print(f"[qpyserve] http://localhost:{port} ({mode})", flush=True)
            uvicorn.run("qpyserve._entry:create_app", factory=True, host=host,
                        port=port, reload=(mode == "development"),
                        workers=workers if mode == "production" else None,
                        reload_dirs=[str(project_dir)] if mode == "development" else None,
                        reload_includes=["*.py"] if mode == "development" else None,
                        reload_excludes=["node_modules", "dist"] if mode == "development" else None)
    finally:
        if vite_process is not None:
            _stop_process(vite_process)
        if generated_config is not None:
            generated_config.unlink(missing_ok=True)
        if previous is None:
            os.environ.pop("QPYSERVE_RUNTIME_CONFIG", None)
        else:
            os.environ["QPYSERVE_RUNTIME_CONFIG"] = previous

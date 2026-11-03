"""Single-command development and production runner for FastAPI + web frontends."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from typing import Literal

from fastapi import FastAPI
import uvicorn

Mode = Literal["development", "production"]


def _has_vite(folder: Path) -> bool:
    manifest = folder / "package.json"
    if not manifest.is_file():
        return False
    data = json.loads(manifest.read_text(encoding="utf-8"))
    dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return "vite" in dependencies


def _npm_install(folder: Path) -> str:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("This frontend uses Vite; install Node.js and npm first.")
    if not (folder / "node_modules" / "vite").is_dir():
        command = [npm, "ci"] if (folder / "package-lock.json").is_file() else [npm, "install"]
        print(f"[qpyserve] Installing frontend packages: {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=folder, check=True)
    return npm


def _vite_config(folder: Path, *, host: str, port: int, backend_port: int) -> Path:
    config = folder / ".qpyserve.vite.config.mjs"
    existing = next((p for p in ("vite.config.ts", "vite.config.mts", "vite.config.js", "vite.config.mjs") if (folder / p).is_file()), None)
    original = f"import userConfig from './{existing}';\n" if existing else "const userConfig = {};\n"
    # JSON encoding protects values passed into the generated JavaScript.
    content = (
        "import { defineConfig, mergeConfig } from 'vite';\n"
        + original
        + "export default defineConfig(async (env) => {\n"
        + "  const base = typeof userConfig === 'function' ? await userConfig(env) : userConfig;\n"
        + "  return mergeConfig(base || {}, { server: {\n"
        + f"    host: {json.dumps(host)}, port: {port}, strictPort: true,\n"
        + "    proxy: {\n"
        + f"      '^/api(?:/|$)': {{ target: 'http://127.0.0.1:{backend_port}', changeOrigin: true, ws: true }},\n"
        + f"      '^/(docs|redoc|openapi.json|__qpyserve)(?:/|$)': {{ target: 'http://127.0.0.1:{backend_port}', changeOrigin: true }}\n"
        + "    }\n"
        + "  }});\n"
        + "});\n"
    )
    config.write_text(content, encoding="utf-8")
    return config


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        # npm.cmd creates a child Node.js process; stop its full tree.
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
) -> None:
    """Run FastAPI and an optional static/Vite frontend under one origin.

    Use `python main.py` for dev, or `python main.py --prod` for production.
    A Vite project is detected by its package.json; HTML-only sites need no Node.
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
    if mode == "development" and workers > 1:
        raise ValueError("Multiple workers are supported only in production")

    script = Path(sys.argv[0]).resolve()
    project_dir = script.parent
    root = Path(frontend)
    if not root.is_absolute():
        root = project_dir / root
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Frontend directory not found: {root}")

    if app_import is None:
        main_globals = vars(sys.modules["__main__"])
        app_var = next((key for key, value in main_globals.items() if value is app and key.isidentifier()), None)
        if not app_var or not script.stem.isidentifier():
            raise ValueError("Cannot locate FastAPI app. Pass app_import='main:app' explicitly.")
        app_import = f"{script.stem}:{app_var}"

    vite = _has_vite(root)
    static_directory = root / dist if vite else root
    if mode == "production" and not (static_directory / "index.html").is_file():
        raise FileNotFoundError(
            f"Built frontend missing: {static_directory / 'index.html'}. "
            "Run 'npm run build' in the frontend folder before production."
        )
    if not vite and not (root / "index.html").is_file():
        raise FileNotFoundError(f"Plain HTML frontend must contain {root / 'index.html'}")

    if vite and mode == "development" and port == 65535:
        raise ValueError("Vite development needs port and port+1; choose port <= 65534")

    config = {
        "app_import": app_import,
        "serve_frontend": not (vite and mode == "development"),
        "static_directory": str(static_directory),
        "live_reload": not vite and mode == "development",
    }
    previous = os.environ.get("QPYSERVE_RUNTIME_CONFIG")
    os.environ["QPYSERVE_RUNTIME_CONFIG"] = json.dumps(config)
    vite_process: subprocess.Popen | None = None
    generated_config: Path | None = None
    try:
        if vite and mode == "development":
            npm = _npm_install(root)
            generated_config = _vite_config(root, host=host, port=port, backend_port=port + 1)
            cmd = [npm, "run", "dev", "--", "--config", generated_config.name]
            kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
            vite_process = subprocess.Popen(cmd, cwd=root, **kwargs)
            print(f"[qpyserve] http://localhost:{port} (Vite) -> /api on localhost:{port+1}", flush=True)
            uvicorn.run("qpyserve._entry:create_app", factory=True, host="127.0.0.1",
                        port=port + 1, reload=True, reload_dirs=[str(project_dir)],
                        reload_excludes=["node_modules", "dist", ".qpyserve.vite.config.mjs"])
        else:
            print(f"[qpyserve] http://localhost:{port} ({mode})", flush=True)
            uvicorn.run("qpyserve._entry:create_app", factory=True, host=host,
                        port=port, reload=(mode == "development"),
                        workers=workers if mode == "production" else None,
                        reload_dirs=[str(project_dir)] if mode == "development" else None,
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

"""Optional Vite tooling; no JavaScript dependency is needed for plain HTML sites."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable


DEFAULT_API_PATHS = ("/api", "/docs", "/redoc", "/openapi.json", "/__qpyserve")


def normalize_api_paths(paths: Iterable[str] | None = None) -> tuple[str, ...]:
    """Explicit API prefixes routed to Python in Vite dev and excluded from SPA fallback."""
    if isinstance(paths, str):
        paths = (paths,)
    ordered = dict.fromkeys(DEFAULT_API_PATHS)
    for path in paths or ():
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
            raise ValueError(f"API path must start with one '/': {path!r}")
        if path == "/" or any(ch in path for ch in ("?", "#", "\\", "*", "\n", "\r")):
            raise ValueError(f"Invalid API proxy prefix: {path!r}")
        path = path.rstrip("/")
        if not path or "//" in path or "/./" in path or "/../" in path or path.endswith(("/.", "/..")):
            raise ValueError(f"Invalid API proxy prefix: {path!r}")
        ordered[path] = None
    return tuple(ordered)


def has_vite(folder: Path) -> bool:
    manifest = folder / "package.json"
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid frontend/package.json: {exc}") from exc
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return "vite" in deps


def package_manager(folder: Path) -> str:
    package_json = json.loads((folder / "package.json").read_text(encoding="utf-8"))
    specified = package_json.get("packageManager", "").split("@", 1)[0]
    if specified:
        if specified not in ("npm", "pnpm", "yarn", "bun"):
            raise ValueError(f"Unsupported package manager: {specified}")
        return specified
    for filename, manager in (
        ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
        ("bun.lock", "bun"), ("bun.lockb", "bun"),
        ("package-lock.json", "npm"), ("npm-shrinkwrap.json", "npm"),
    ):
        if (folder / filename).is_file():
            return manager
    return "npm"


def _manager_command(manager: str) -> list[str]:
    executable = shutil.which(manager)
    if executable:
        return [executable]
    if manager in ("pnpm", "yarn"):
        corepack = shutil.which("corepack")
        if corepack:
            return [corepack, manager]
    raise RuntimeError(
        f"Frontend requires {manager!r}, but it is not installed. "
        "Install Node.js and the selected package manager (or Corepack). "
        "Plain HTML frontends need no JavaScript tooling."
    )


def ensure_dependencies(folder: Path, manager: str) -> list[str]:
    command = _manager_command(manager)
    vite_bin = folder / "node_modules" / "vite"
    pnp = folder / ".pnp.cjs"
    if vite_bin.exists() or (manager == "yarn" and pnp.is_file()):
        return command
    install_args = {"npm": ["install"], "pnpm": ["install"],
                    "yarn": ["install"], "bun": ["install"]}[manager]
    if manager == "npm" and any((folder / n).is_file() for n in ("package-lock.json", "npm-shrinkwrap.json")):
        install_args = ["ci"]
    if manager == "pnpm" and (folder / "pnpm-lock.yaml").is_file():
        install_args = ["install", "--frozen-lockfile"]
    print(f"[qpyserve] Installing frontend dependencies ({manager})", flush=True)
    subprocess.run([*command, *install_args], cwd=folder, check=True)
    return command


def vite_command(manager_cmd: list[str], manager: str, *args: str) -> list[str]:
    # Invoke local Vite directly: package.json does not need a `dev` or `build` script.
    if manager == "npm":
        return [*manager_cmd, "exec", "--no", "--", "vite", *args]
    if manager == "pnpm":
        return [*manager_cmd, "exec", "vite", *args]
    if manager == "yarn":
        return [*manager_cmd, "vite", *args]
    return [*manager_cmd, "x", "--no-install", "vite", *args]


def build_frontend(folder: Path) -> None:
    manager = package_manager(folder)
    command = ensure_dependencies(folder, manager)
    manifest = json.loads((folder / "package.json").read_text(encoding="utf-8"))
    if "build" in manifest.get("scripts", {}):
        args = ["run", "build"] if manager in ("npm", "pnpm", "bun") else ["build"]
        cmd = [*command, *args]
    else:
        cmd = vite_command(command, manager, "build")
    print("[qpyserve] Building frontend", flush=True)
    subprocess.run(cmd, cwd=folder, check=True)


def vite_config(folder: Path, *, host: str, port: int, backend_port: int,
                api_paths: Iterable[str] = DEFAULT_API_PATHS) -> Path:
    config = folder / ".qpyserve.vite.config.mjs"
    existing = next((p for p in (
        "vite.config.ts", "vite.config.mts", "vite.config.js", "vite.config.mjs",
        "vite.config.cts", "vite.config.cjs"
    ) if (folder / p).is_file()), None)
    original = f"import userConfig from './{existing}';\n" if existing else "const userConfig = {};\n"
    proxies = {
        f"^{re.escape(path)}(?:/|$)": {
            "target": f"http://127.0.0.1:{backend_port}",
            "changeOrigin": True,
            "ws": True,
        }
        for path in api_paths
    }
    server = {"host": host, "port": port, "strictPort": True, "proxy": proxies}
    config.write_text(
        "import { defineConfig, mergeConfig } from 'vite';\n"
        + original
        + "export default defineConfig(async (env) => {\n"
        + "  const base = typeof userConfig === 'function' ? await userConfig(env) : userConfig;\n"
        + f"  return mergeConfig(base || {{}}, {{ server: {json.dumps(server)} }});\n"
        + "});\n",
        encoding="utf-8",
    )
    return config

"""Serve an HTML/JS site or a built SPA through an existing FastAPI app."""

from __future__ import annotations

from pathlib import Path
import re
import time
from threading import Lock
from typing import Iterable

from ._tooling import normalize_api_paths

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

_RELOAD_SCRIPT = """<script>
(() => {
  let known;
  async function check() {
    try {
      const response = await fetch('/__qpyserve/version', {cache: 'no-store'});
      if (!response.ok) return;
      const current = (await response.json()).version;
      if (known !== undefined && known !== current) location.reload();
      known = current;
    } catch (_) { /* Server may be restarting. */ }
  }
  check();
  setInterval(check, 1200);
})();
</script>"""


def _version(folder: Path) -> int:
    """Latest edit time; used only for small local static sites in dev."""
    latest = 0
    for file in folder.rglob("*"):
        if any(part in {"node_modules", ".git", "dist", "__pycache__"} for part in file.parts):
            continue
        if file.is_file():
            try:
                latest = max(latest, file.stat().st_mtime_ns)
            except OSError:
                pass
    return latest


_PRIVATE_FILENAMES = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml",
    "yarn.lock", "bun.lock", "bun.lockb", "id_rsa", "id_ed25519",
    "credentials.json", "secrets.json",
}
_PRIVATE_SUFFIXES = (
    ".py", ".pyc", ".pem", ".key", ".p12", ".pfx", ".sqlite",
    ".sqlite3", ".db", ".map",
)
# Files under the static root must be browser assets. Serve other types through
# explicit FastAPI endpoints, with authorization where appropriate.
_PUBLIC_SUFFIXES = frozenset({
    ".html", ".htm", ".css", ".js", ".mjs", ".json", ".webmanifest",
    ".txt", ".xml", ".csv", ".geojson", ".pbf", ".mvt", ".pmtiles",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico",
    ".avif", ".apng", ".bmp", ".woff", ".woff2", ".ttf",
    ".otf", ".eot", ".wasm", ".pdf", ".webm", ".mp3", ".mp4",
    ".bin", ".glb", ".gltf",
})
_FINGERPRINTED_ASSET = re.compile(r"-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$")


def _blocked(parts: tuple[str, ...]) -> bool:
    """Do not serve development files or credentials under a public directory."""
    for part in parts:
        name = part.lower()
        if (name.startswith(".") or name in _PRIVATE_FILENAMES
                or name in {"node_modules", "__pycache__"}
                or name.startswith("vite.config.")
                or name.endswith(_PRIVATE_SUFFIXES)):
            return True
    return False


def _public_asset(file: Path) -> bool:
    """Deny unfamiliar asset types; expose them through explicit API routes."""
    return file.suffix.lower() in _PUBLIC_SUFFIXES


def _safe_file(root: Path, file: Path) -> Path:
    """Resolve every final target, including symlinks used by directory index files."""
    target = file.resolve()
    if not target.is_relative_to(root) or _blocked(target.relative_to(root).parts):
        raise HTTPException(404, "Not found")
    return target


def attach_frontend(app: FastAPI, directory: str | Path, *, live_reload: bool = False,
                    api_paths: Iterable[str] | None = None,
                    built_vite: bool = False, trace_enabled: bool = False) -> FastAPI:
    """Attach last, after the caller has registered all API routes.

    Unknown /api paths never return the SPA index. Non-existent assets return 404.
    """
    reserved_paths = normalize_api_paths(api_paths)
    root = Path(directory).resolve()
    # Do not trust an index.html symlink pointing outside the public directory
    # (or at an internal secret). This also protects SPA history fallbacks.
    try:
        entrypoint = _safe_file(root, root / "index.html")
    except HTTPException as exc:
        raise ValueError("Frontend index.html must be a public file inside its directory") from exc
    if not entrypoint.is_file():
        raise FileNotFoundError(f"No index.html found in {root}")

    @app.get("/__qpyserve/health", include_in_schema=False)
    def qpyserve_health() -> dict[str, str]:
        return {"status": "ok"}

    last_scan = [0.0, 0]
    scan_lock = Lock()

    if live_reload:
        @app.get("/__qpyserve/version", include_in_schema=False)
        def qpyserve_version() -> dict[str, int]:
            # Multiple open tabs share one scan per second, not one scan per request.
            with scan_lock:
                now = time.monotonic()
                if now - last_scan[0] >= 0.75:
                    last_scan[:] = [now, _version(root)]
                return {"version": last_scan[1]}

    # Keep missing API paths distinct from static frontend routes, for all methods.
    @app.api_route(
        "/api/{unmatched_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=False,
    )
    async def unknown_api(unmatched_path: str):
        raise HTTPException(404, "API endpoint not found")

    @app.api_route("/{asset_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def frontend_asset(asset_path: str, request: Request):
        requested = "/" + asset_path
        if any(requested == prefix or requested.startswith(prefix + "/")
               for prefix in reserved_paths):
            raise HTTPException(404, "Not found")

        parts = Path(asset_path).parts
        if _blocked(parts):
            raise HTTPException(404, "Not found")

        candidate = _safe_file(root, root / asset_path)
        if candidate.is_dir():
            candidate = _safe_file(root, candidate / "index.html")
        if not candidate.is_file():
            # Single-page app history fallback, but not for missing JS/CSS/images.
            if "." not in Path(asset_path).name and "text/html" in request.headers.get("accept", ""):
                candidate = entrypoint
            else:
                raise HTTPException(404, "Not found")

        if not _public_asset(candidate):
            raise HTTPException(404, "Not found")

        # A stale SPA entrypoint often causes the "hard refresh required" symptom.
        # Only static responses receive these headers; APIs control their own.
        headers = {"X-Content-Type-Options": "nosniff"}
        if live_reload:
            headers["Cache-Control"] = "no-store"
        elif candidate.suffix.lower() == ".html":
            headers["Cache-Control"] = "no-cache"
        elif (built_vite and parts[:1] == ("assets",)
              and _FINGERPRINTED_ASSET.search(candidate.name)):
            headers["Cache-Control"] = "public, max-age=31536000, immutable"
        if live_reload and candidate.suffix.lower() == ".html":
            html = candidate.read_text(encoding="utf-8")
            scripts = _RELOAD_SCRIPT
            if trace_enabled:
                scripts += '<script defer src="/__qpyserve/trace.js"></script>'
            html = html.replace("</body>", f"{scripts}</body>") if "</body>" in html else html + scripts
            return HTMLResponse(html, headers=headers)
        return FileResponse(candidate, headers=headers)

    return app

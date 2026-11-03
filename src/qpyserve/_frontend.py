"""Serve an HTML/JS site or a built SPA through an existing FastAPI app."""

from __future__ import annotations

from pathlib import Path
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


def attach_frontend(app: FastAPI, directory: str | Path, *, live_reload: bool = False,
                    api_paths: Iterable[str] | None = None) -> FastAPI:
    """Attach last, after the caller has registered all API routes.

    Unknown /api paths never return the SPA index. Non-existent assets return 404.
    """
    reserved_paths = normalize_api_paths(api_paths)
    root = Path(directory).resolve()
    if not (root / "index.html").is_file():
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

    @app.get("/{asset_path:path}", include_in_schema=False)
    async def frontend_asset(asset_path: str, request: Request):
        requested = "/" + asset_path
        if any(requested == prefix or requested.startswith(prefix + "/")
               for prefix in reserved_paths):
            raise HTTPException(404, "Not found")

        parts = Path(asset_path).parts
        # A plain HTML frontend is a directory, not an invitation to publish its
        # .env, package manager files, Python sources, or development config.
        if any(part.startswith(".") for part in parts) or any(
            part in {"node_modules", "__pycache__", "package.json", "package-lock.json",
                     "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb"}
            or part.startswith("vite.config.") or part.endswith((".py", ".pyc"))
            for part in parts
        ):
            raise HTTPException(404, "Not found")

        candidate = (root / asset_path).resolve()
        if not candidate.is_relative_to(root):
            raise HTTPException(404, "Not found")
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            # Single-page app history fallback, but not for missing JS/CSS/images.
            if "." not in Path(asset_path).name and "text/html" in request.headers.get("accept", ""):
                candidate = root / "index.html"
            else:
                raise HTTPException(404, "Not found")

        # A stale SPA entrypoint often causes the "hard refresh required" symptom.
        headers = ({"Cache-Control": "no-store"} if live_reload else
                   {"Cache-Control": "no-cache"} if candidate.suffix.lower() == ".html" else {})
        if live_reload and candidate.suffix.lower() == ".html":
            html = candidate.read_text(encoding="utf-8")
            script = _RELOAD_SCRIPT
            html = html.replace("</body>", f"{script}</body>") if "</body>" in html else html + script
            return HTMLResponse(html, headers=headers)
        return FileResponse(candidate, headers=headers)

    return app

"""Local, bounded, development-only request diagnostics.

Never collect request bodies, headers, cookies, raw URL paths, or query strings.
Browser-supplied correlation IDs are identifiers only, never authentication.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from importlib.resources import files
import json
from pathlib import Path
import re
from threading import Lock
import time
import traceback
from typing import Any, Iterable
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_TRACE_ID = re.compile(r"^[a-f0-9]{12,32}$")
_LOCAL_ORIGINS = {"localhost", "127.0.0.1", "[::1]"}


class TraceStore:
    """Thread-safe, bounded diagnostic metadata for a single development worker."""

    def __init__(self, limit: int = 100) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=limit)
        self._lock = Lock()

    def record(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries)


def _exception_location(exc: Exception, project_root: Path) -> str | None:
    """Return only a Python source path relative to the application directory."""
    root = project_root.resolve()
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        source = Path(frame.filename).resolve()
        if source.is_relative_to(root):
            relative = source.relative_to(root)
            if relative.suffix == ".py" and not any(part.startswith(".") for part in relative.parts):
                return f"{relative.as_posix()}:{frame.lineno}"
    return None


def classify_failure(status: int, exception: bool = False) -> str:
    """Classify observed evidence without inventing a root cause."""
    if exception:
        return "python_exception"
    if status == 429:
        return "rate_limited"
    if status in {401, 403}:
        return "access_denied"
    if status == 404:
        return "not_found"
    if status >= 500:
        return "server_error"
    if status >= 400:
        return "client_error"
    return "ok"


def _correlation_id(scope: Scope) -> str:
    """Use a strictly validated client ID so failures can match an absent 500 response."""
    for key, value in scope.get("headers", ()):
        if key.lower() == b"x-qpyserve-trace-id":
            try:
                claimed = value.decode("ascii")
            except UnicodeDecodeError:
                break
            if _TRACE_ID.fullmatch(claimed):
                return claimed
            break
    return uuid4().hex[:16]


class TraceMiddleware:
    """ASGI timing, correlated IDs and source references for configured API prefixes."""

    def __init__(
        self,
        app: ASGIApp,
        store: TraceStore,
        paths: tuple[str, ...],
        project_root: Path,
    ) -> None:
        self.app = app
        self.store = store
        self.paths = tuple(p for p in paths if p != "/__qpyserve")
        self.project_root = project_root

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path.startswith("/__qpyserve/") or not any(
            path == prefix or path.startswith(prefix + "/") for prefix in self.paths
        ):
            await self.app(scope, receive, send)
            return

        request_id = _correlation_id(scope)
        started = time.perf_counter()
        status = 500
        error: dict[str, str] = {}

        async def correlated_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = dict(message)
                headers = [
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() != b"x-qpyserve-trace-id"
                ]
                headers.append((b"x-qpyserve-trace-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, correlated_send)
        except Exception as exc:
            status = 500
            error["exception"] = type(exc).__name__
            location = _exception_location(exc, self.project_root)
            if location:
                error["source"] = location
            raise
        finally:
            route = scope.get("route")
            template = getattr(route, "path", None)
            self.store.record({
                "id": request_id,
                "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "method": scope.get("method", "GET"),
                "route": template if isinstance(template, str) else "(unmatched API route)",
                "status": status,
                "category": classify_failure(status, bool(error)),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                **error,
            })


def install_trace(app: FastAPI, paths: Iterable[str], project_root: str | Path = ".") -> None:
    """Add development-only routes; call before FastAPI handles requests."""
    configured = tuple(p for p in paths if p != "/__qpyserve")
    store = TraceStore()
    root = Path(project_root).resolve()

    @app.get("/__qpyserve/trace", include_in_schema=False)
    def trace_snapshot(request: Request) -> JSONResponse:
        # Even when an app enables permissive CORS, cross-site browsers must
        # not read local diagnostic metadata.
        site = request.headers.get("sec-fetch-site", "").lower()
        if site not in {"", "same-origin", "none"}:
            raise HTTPException(403, "Local development diagnostics only")
        return JSONResponse(
            {"version": 2, "requests": store.snapshot()},
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Cross-Origin-Resource-Policy": "same-origin",
            },
        )

    @app.get("/__qpyserve/trace.js", include_in_schema=False)
    def trace_client() -> Response:
        source = files("qpyserve").joinpath("_trace_client.js").read_text(encoding="utf-8")
        source = source.replace("__QPYSERVE_API_PATHS__", json.dumps(configured))
        return Response(
            source,
            media_type="text/javascript",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    app.add_middleware(
        TraceMiddleware, store=store, paths=configured, project_root=root,
    )

"""Development-only API traces for the local QPyServe diagnostic panel.

No request or response bodies, headers, cookies, query strings, or client IPs are stored.
The bounded in-memory buffer is never enabled automatically in production.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from threading import Lock
import time
import traceback
from typing import Any, Iterable
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class TraceStore:
    """Bounded, per-process recent requests for one development worker."""

    def __init__(self, limit: int = 100) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=limit)
        self._lock = Lock()

    def record(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries)


def _exception_location(exc: Exception) -> str | None:
    """Avoid exposing absolute filesystem paths in copied diagnostics."""
    project = Path.cwd().resolve()
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        source = Path(frame.filename).resolve()
        if source.is_relative_to(project):
            relative = source.relative_to(project)
            if not any(part.startswith(".") for part in relative.parts):
                return f"{relative.as_posix()}:{frame.lineno}"
    return None


class TraceMiddleware:
    """ASGI middleware records API timing and a response correlation ID."""

    def __init__(self, app: ASGIApp, store: TraceStore, paths: tuple[str, ...]) -> None:
        self.app = app
        self.store = store
        self.paths = tuple(p for p in paths if p != "/__qpyserve")

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

        request_id = uuid4().hex[:12]
        start = time.perf_counter()
        status = 500
        error: dict[str, str] = {}

        async def traced_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = dict(message)
                headers = list(message.get("headers", []))
                headers.append((b"x-qpyserve-trace-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, traced_send)
        except Exception as exc:
            status = 500
            error["exception"] = type(exc).__name__
            location = _exception_location(exc)
            if location:
                error["source"] = location
            raise
        finally:
            route = scope.get("route")
            # Known FastAPI route templates omit user-supplied path parameter values.
            pattern = getattr(route, "path", None)
            route_name = pattern if isinstance(pattern, str) else "(unmatched API path)"
            self.store.record({
                "id": request_id,
                "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "method": scope.get("method", "GET"),
                "route": route_name,
                "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                **error,
            })


def install_trace(app: FastAPI, paths: Iterable[str]) -> None:
    """Install local-only trace routes and middleware before the server starts."""
    store = TraceStore()

    @app.get("/__qpyserve/trace", include_in_schema=False)
    def trace_snapshot() -> JSONResponse:
        return JSONResponse(
            {"version": 1, "requests": store.snapshot()},
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/__qpyserve/trace.js", include_in_schema=False)
    def trace_client() -> Response:
        source = files("qpyserve").joinpath("_trace_client.js").read_text(encoding="utf-8")
        return Response(
            source,
            media_type="text/javascript",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    app.add_middleware(TraceMiddleware, store=store, paths=tuple(paths))

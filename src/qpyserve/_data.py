"""Opt-in, bounded analytical datasets for FastAPI + JavaScript applications.

Data Bridge runs DuckDB relations lazily and moves only requested rows/columns.
No DuckDB, Arrow, or JavaScript dependencies are imported by ordinary QPyServe apps.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from importlib.util import find_spec
import logging
import math
from pathlib import Path
import re
from typing import Any, Callable, Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

_LOG = logging.getLogger("qpyserve.data")
_DATASET_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_MAX_FILTERS = 20
_MAX_IN_VALUES = 100
_MAX_VALUE_LENGTH = 4096
_ARROW_MIME = "application/vnd.apache.arrow.stream"

# A provider is invoked per request with a fresh DuckDB connection and Request.
# Providers are responsible for applying tenant scoping when appropriate.
Provider = Callable[[Any, Request], Any]


class DataFilter(BaseModel):
    """A safe, typed predicate. Raw SQL from browsers is never supported."""

    model_config = ConfigDict(extra="forbid")
    column: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "is_null", "is_not_null"]
    value: Any = None


class DataSort(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str
    desc: bool = False


class DataQuery(BaseModel):
    """Projection/filter/sort/page constraints, executed within DuckDB."""

    model_config = ConfigDict(extra="forbid")
    columns: list[str] | None = Field(default=None, max_length=100)
    filters: list[DataFilter] = Field(default_factory=list, max_length=_MAX_FILTERS)
    sort: list[DataSort] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=1000, ge=1)
    offset: int = Field(default=0, ge=0, le=1_000_000)


@dataclass(frozen=True)
class _Dataset:
    provider: Provider
    description: str = ""


def _duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "Data Bridge requires the optional data dependencies: "
            "python -m pip install 'qpyserve[data]'"
        ) from exc
    return duckdb


def _quote_name(name: str) -> str:
    # Called only after verifying a column belongs to the registered dataset.
    return '"' + name.replace('"', '""') + '"'


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if type(value) is bool:
        return "TRUE" if value else "FALSE"
    if type(value) is int:
        return str(value)
    if type(value) is float:
        if not math.isfinite(value):
            raise HTTPException(status_code=422, detail="Filter numbers must be finite")
        return repr(value)
    if type(value) is str:
        if len(value) > _MAX_VALUE_LENGTH:
            raise HTTPException(status_code=422, detail="Filter string is too long")
        return "'" + value.replace("'", "''") + "'"
    raise HTTPException(
        status_code=422,
        detail="Filter values must be strings, finite numbers, booleans, or null",
    )


def _predicate(term: DataFilter, allowed: set[str]) -> str:
    if term.column not in allowed:
        raise HTTPException(status_code=422, detail=f"Unknown filter column: {term.column}")
    column = _quote_name(term.column)
    if term.op == "is_null":
        return column + " IS NULL"
    if term.op == "is_not_null":
        return column + " IS NOT NULL"
    if term.op in ("in", "not_in"):
        values = term.value
        if not isinstance(values, list) or len(values) > _MAX_IN_VALUES:
            raise HTTPException(status_code=422, detail="IN needs a list of up to 100 values")
        if any(v is None for v in values):
            raise HTTPException(status_code=422, detail="Use is_null for null comparisons")
        if not values:
            return "TRUE" if term.op == "not_in" else "FALSE"
        operator = "NOT IN" if term.op == "not_in" else "IN"
        return column + " " + operator + " (" + ", ".join(map(_sql_literal, values)) + ")"
    if term.value is None:
        if term.op == "eq":
            return column + " IS NULL"
        if term.op == "ne":
            return column + " IS NOT NULL"
        raise HTTPException(status_code=422, detail="Use is_null for null comparisons")
    operator = {
        "eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="
    }[term.op]
    return column + " " + operator + " " + _sql_literal(term.value)


def _apply_query(relation: Any, query: DataQuery, max_limit: int) -> Any:
    if query.limit > max_limit:
        raise HTTPException(status_code=422, detail=f"limit must be <= {max_limit}")
    names = list(relation.columns)
    if len(set(names)) != len(names):
        raise HTTPException(status_code=422, detail="Dataset contains duplicate column names")
    allowed = set(names)
    for term in query.filters:
        relation = relation.filter(_predicate(term, allowed))
    if query.sort:
        for item in query.sort:
            if item.column not in allowed:
                raise HTTPException(status_code=422, detail=f"Unknown sort column: {item.column}")
        clause = ", ".join(
            _quote_name(s.column) + (" DESC" if s.desc else " ASC")
            for s in query.sort
        )
        relation = relation.order(clause)
    if query.columns is not None:
        if not query.columns or len(set(query.columns)) != len(query.columns):
            raise HTTPException(status_code=422, detail="Select unique, nonempty columns")
        for name in query.columns:
            if name not in allowed:
                raise HTTPException(status_code=422, detail=f"Unknown column: {name}")
        relation = relation.project(", ".join(_quote_name(n) for n in query.columns))
    return relation


class _ArrowSink:
    """Collect just the chunks emitted by the current record batch, not the whole result."""

    def __init__(self) -> None:
        self.chunks: deque[bytes] = deque()
        self.closed = False

    def write(self, data: Any) -> int:
        chunk = bytes(data)
        self.chunks.append(chunk)
        return len(chunk)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def drain(self):
        while self.chunks:
            yield self.chunks.popleft()


class DataBridge:
    """Mount an explicit, authenticated-or-public, read-only Data Bridge.

    Example:
        bridge = DataBridge(app, public=True)
        bridge.parquet("pipes", "data/pipes.parquet")

    Authenticated applications should instead pass FastAPI dependencies:
        bridge = DataBridge(app, dependencies=[Depends(require_user)])
        bridge.relation("mine", lambda con, req: con.sql("...tenant-scoped..."))

    HTTP: GET /api/data/{dataset}; POST /api/data/{dataset}/query?format=json|arrow.
    """

    def __init__(
        self,
        app: FastAPI,
        *,
        prefix: str = "/api/data",
        dependencies: list[Any] | None = None,
        public: bool = False,
        max_limit: int = 10_000,
    ) -> None:
        if not isinstance(app, FastAPI):
            raise TypeError("DataBridge expects a FastAPI app")
        if not public and not dependencies:
            raise ValueError(
                "Data Bridge must be protected with dependencies=[Depends(...)] "
                "or intentionally exposed using public=True"
            )
        if not prefix.startswith("/") or prefix == "/" or prefix.endswith("/"):
            raise ValueError("prefix must be an absolute, non-root path without trailing slash")
        if max_limit < 1 or max_limit > 100_000:
            raise ValueError("max_limit must be between 1 and 100000")
        self._datasets: dict[str, _Dataset] = {}
        self._max_limit = max_limit
        # This JavaScript module is public static code. Authenticated data routes
        # remain separately protected, including metadata and queries.
        script_router = APIRouter(prefix=prefix)
        router = APIRouter(prefix=prefix, dependencies=dependencies or [])

        @script_router.get("/_client.js", include_in_schema=False)
        def client_script():
            script = Path(__file__).with_name("_data_client.js").read_text("utf-8")
            return Response(script, media_type="text/javascript", headers={
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"
            })

        @router.get("/{dataset}", include_in_schema=True)
        def schema(dataset: str, request: Request):
            item = self._get(dataset)
            conn = _duckdb().connect(database=":memory:")
            try:
                relation = item.provider(conn, request)
                return JSONResponse(
                    content={
                        "name": dataset,
                        "description": item.description,
                        "columns": [
                            {"name": name, "type": str(typ)}
                            for name, typ in zip(relation.columns, relation.types)
                        ],
                        "default_limit": min(1000, self._max_limit),
                        "max_limit": self._max_limit,
                        "formats": ["json", "arrow"] if find_spec("pyarrow") else ["json"],
                    },
                    headers={"Cache-Control": "private, no-store"},
                )
            except HTTPException:
                raise
            except Exception as exc:
                _LOG.exception("Failed to inspect Data Bridge dataset %s", dataset)
                raise HTTPException(status_code=500, detail="Dataset is unavailable") from exc
            finally:
                conn.close()

        @router.post("/{dataset}/query")
        def query(
            dataset: str,
            payload: DataQuery,
            request: Request,
            format: Literal["json", "arrow"] = "json",
        ):
            item = self._get(dataset)
            if payload.limit > self._max_limit:
                raise HTTPException(
                    status_code=422, detail=f"limit must be <= {self._max_limit}"
                )
            headers = {
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            }
            if format == "arrow":
                if find_spec("pyarrow") is None:
                    raise HTTPException(
                        status_code=501,
                        detail="Arrow responses require python -m pip install 'qpyserve[data]'",
                    )
                # Preflight validation must happen before streaming sends HTTP 200.
                # No rows are fetched here; DuckDB only binds the lazy query.
                conn = _duckdb().connect(database=":memory:")
                try:
                    _apply_query(item.provider(conn, request), payload, self._max_limit)
                except HTTPException:
                    raise
                except Exception as exc:
                    _LOG.exception("Data Bridge Arrow query could not be prepared")
                    raise HTTPException(status_code=422, detail="Invalid dataset query") from exc
                finally:
                    conn.close()
                return StreamingResponse(
                    self._stream_arrow(item, payload, request),
                    media_type=_ARROW_MIME,
                    headers=headers,
                )
            return self._query_json(item, payload, request, headers)

        app.include_router(script_router)
        app.include_router(router)

    def _get(self, name: str) -> _Dataset:
        try:
            return self._datasets[name]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown dataset") from exc

    def relation(self, name: str, provider: Provider, *, description: str = "") -> None:
        """Register a per-request DuckDB relation provider; no client SQL is accepted."""
        if not _DATASET_NAME.fullmatch(name) or name.startswith("_"):
            raise ValueError("Dataset names must start with a letter and use letters/numbers/_/-")
        if name in self._datasets:
            raise ValueError(f"Dataset already registered: {name}")
        if not callable(provider):
            raise TypeError("provider must be callable(conn, request)")
        self._datasets[name] = _Dataset(provider=provider, description=description)

    def parquet(self, name: str, path: str | Path, *, description: str = "") -> None:
        """Read Parquet lazily. Path is server-owned and never accepted from the browser."""
        source = str(Path(path).resolve())
        self.relation(
            name,
            lambda con, _request: con.read_parquet(source),
            description=description,
        )

    def _query_json(
        self,
        item: _Dataset,
        payload: DataQuery,
        request: Request,
        headers: dict[str, str],
    ):
        conn = _duckdb().connect(database=":memory:")
        try:
            relation = _apply_query(item.provider(conn, request), payload, self._max_limit)
            names = list(relation.columns)
            rows = relation.limit(payload.limit + 1, payload.offset).fetchall()
            has_more = len(rows) > payload.limit
            rows = rows[:payload.limit]
            result = {
                "rows": [dict(zip(names, row)) for row in rows],
                "limit": payload.limit,
                "offset": payload.offset,
                "has_more": has_more,
            }
            return JSONResponse(content=jsonable_encoder(result), headers=headers)
        except HTTPException:
            raise
        except Exception as exc:
            _LOG.exception("Data Bridge JSON query failed")
            raise HTTPException(status_code=500, detail="Dataset query failed") from exc
        finally:
            conn.close()

    def _stream_arrow(self, item: _Dataset, payload: DataQuery, request: Request):
        # The generator runs in the FastAPI thread pool. Create connections in this
        # thread; do not share one DuckDB connection across concurrent requests.
        import pyarrow as pa

        conn = _duckdb().connect(database=":memory:")
        try:
            relation = _apply_query(item.provider(conn, request), payload, self._max_limit)
            bounded = relation.limit(payload.limit, payload.offset)
            reader = bounded.to_arrow_reader(batch_size=min(payload.limit, 2048))
            sink = _ArrowSink()
            with pa.ipc.new_stream(sink, reader.schema) as writer:
                yield from sink.drain()
                for batch in reader:
                    writer.write_batch(batch)
                    yield from sink.drain()
            yield from sink.drain()
        finally:
            conn.close()

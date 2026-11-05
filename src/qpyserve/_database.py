"""Optional read-only SQL database table sources for Data Bridge.

SQLAlchemy is imported lazily, only when a registered database source is queried.
All browser predicates use SQLAlchemy bound parameters and known table columns.
The database server performs filtering, projection, sorting, and pagination.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from functools import cached_property
import math
import os
import re
from typing import Any

from fastapi import HTTPException

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_IN_VALUES = 100
_MAX_VALUE_LENGTH = 4096


@dataclass(frozen=True)
class DatabaseSource:
    table: str
    url_env: str = "DATABASE_URL"
    schema: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.table):
            raise ValueError("table must be one SQL table or view name, without raw SQL")
        if self.schema is not None and not _IDENTIFIER.fullmatch(self.schema):
            raise ValueError("schema must be one SQL schema name")
        if self.updated_at is not None and not _IDENTIFIER.fullmatch(self.updated_at):
            raise ValueError("updated_at must be a column name")
        if not _IDENTIFIER.fullmatch(self.url_env):
            raise ValueError("url_env must be an environment variable name")


def db(
    table: str,
    *,
    url_env: str = "DATABASE_URL",
    schema: str | None = None,
    updated_at: str | None = None,
) -> DatabaseSource:
    """Describe a server-side database table; no connection is made yet.

    Example:
        db("DailyPumpage", schema="dbo", url_env="DWO_DB_URL", updated_at="ModifiedAt")

    Use a database account restricted to read-only tables/views.
    The connection URI stays in the server's environment, never in frontend JS.
    """
    if "." in table and schema is None:
        parts = table.split(".")
        if len(parts) != 2:
            raise ValueError("Use table='name', schema='schema' for a database table")
        schema, table = parts
    return DatabaseSource(table, url_env=url_env, schema=schema, updated_at=updated_at)


def _sqlalchemy():
    try:
        import sqlalchemy
    except ImportError as exc:
        raise RuntimeError(
            "Database sources need SQLAlchemy: pip install 'qpyserve[database]' "
            "and an appropriate database driver"
        ) from exc
    return sqlalchemy


def _check_scalar(value: Any) -> Any:
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise HTTPException(status_code=422, detail="Filter number must be finite")
        return value
    if type(value) is str:
        if len(value) > _MAX_VALUE_LENGTH:
            raise HTTPException(status_code=422, detail="Filter string too long")
        return value
    raise HTTPException(status_code=422, detail="Filter value must be a JSON scalar")


def _coerce_for_column(value: Any, column: Any) -> Any:
    value = _check_scalar(value)
    if value is None or not isinstance(value, str):
        return value
    sa = _sqlalchemy()
    try:
        if isinstance(column.type, sa.DateTime):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(column.type, sa.Date):
            return date.fromisoformat(value)
        if isinstance(column.type, sa.Time):
            return time.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid ISO date/time filter") from exc
    return value


class DatabaseReader:
    def __init__(self, source: DatabaseSource) -> None:
        self.source = source

    @cached_property
    def engine(self):
        sa = _sqlalchemy()
        url = os.environ.get(self.source.url_env)
        if not url:
            raise RuntimeError(
                f"Database connection environment variable {self.source.url_env} is unset"
            )
        # Pooling and connection health are handled by SQLAlchemy; the database
        # driver is chosen in the server-only SQLAlchemy URL.
        return sa.create_engine(url, pool_pre_ping=True)

    @cached_property
    def table(self):
        sa = _sqlalchemy()
        metadata = sa.MetaData()
        table = sa.Table(
            self.source.table,
            metadata,
            schema=self.source.schema,
            autoload_with=self.engine,
        )
        if not table.columns:
            raise RuntimeError("Database table has no columns")
        if self.source.updated_at and self.source.updated_at not in table.c:
            raise RuntimeError("updated_at column does not exist")
        return table

    def schema(self) -> list[dict[str, str]]:
        return [
            {"name": col.name, "type": str(col.type)}
            for col in self.table.columns
        ]

    def version(self) -> str | None:
        if self.source.updated_at is None:
            return None
        sa = _sqlalchemy()
        column = self.table.c[self.source.updated_at]
        with self.engine.connect() as connection:
            value = connection.execute(sa.select(sa.func.max(column))).scalar()
        return str(value) if value is not None else None

    def _query(self, payload: Any, max_limit: int):
        sa = _sqlalchemy()
        table = self.table
        allowed = set(table.c.keys())
        if payload.limit > max_limit:
            raise HTTPException(status_code=422, detail=f"limit must be <= {max_limit}")

        if payload.columns is not None:
            if not payload.columns or len(payload.columns) != len(set(payload.columns)):
                raise HTTPException(status_code=422, detail="Select unique, nonempty columns")
            if any(name not in allowed for name in payload.columns):
                raise HTTPException(status_code=422, detail="Unknown requested column")
            selected = [table.c[name] for name in payload.columns]
        else:
            selected = list(table.columns)
        query = sa.select(*selected)

        for item in payload.filters:
            if item.column not in allowed:
                raise HTTPException(status_code=422, detail="Unknown filter column")
            col = table.c[item.column]
            if item.op == "is_null":
                predicate = col.is_(None)
            elif item.op == "is_not_null":
                predicate = col.is_not(None)
            elif item.op in {"in", "not_in"}:
                values = item.value
                if not isinstance(values, list) or len(values) > _MAX_IN_VALUES:
                    raise HTTPException(status_code=422, detail="IN accepts up to 100 values")
                if any(v is None for v in values):
                    raise HTTPException(status_code=422, detail="Use is_null for null")
                params = [_coerce_for_column(v, col) for v in values]
                predicate = col.not_in(params) if item.op == "not_in" else col.in_(params)
            else:
                value = _coerce_for_column(item.value, col)
                comparisons = {
                    "eq": lambda v: col.is_(None) if v is None else col == v,
                    "ne": lambda v: col.is_not(None) if v is None else col != v,
                    "gt": lambda v: col > v,
                    "gte": lambda v: col >= v,
                    "lt": lambda v: col < v,
                    "lte": lambda v: col <= v,
                }
                if value is None and item.op not in ("eq", "ne"):
                    raise HTTPException(status_code=422, detail="Use is_null for null")
                predicate = comparisons[item.op](value)
            query = query.where(predicate)

        if payload.sort:
            for item in payload.sort:
                if item.column not in allowed:
                    raise HTTPException(status_code=422, detail="Unknown sort column")
            ordering = [
                table.c[item.column].desc() if item.desc else table.c[item.column].asc()
                for item in payload.sort
            ]
        else:
            # MSSQL OFFSET requires ORDER BY. Prefer a primary key, and fall
            # back to the first column. Nonunique sorting can be unstable.
            pk = list(table.primary_key.columns)
            ordering = [col.asc() for col in (pk if pk else list(table.columns)[:1])]
        return query.order_by(*ordering).limit(payload.limit + 1).offset(payload.offset)

    def query_page(self, payload: Any, max_limit: int) -> dict[str, Any]:
        query = self._query(payload, max_limit)
        with self.engine.connect() as conn:
            result = conn.execute(query)
            names = list(result.keys())
            rows = result.fetchmany(payload.limit + 1)
        has_more = len(rows) > payload.limit
        return {
            "rows": [dict(zip(names, row, strict=True)) for row in rows[:payload.limit]],
            "limit": payload.limit,
            "offset": payload.offset,
            "has_more": has_more,
        }

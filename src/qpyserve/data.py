"""Optional big-data-first Data Bridge APIs.

Install with `python -m pip install "qpyserve[data]"`.
Regular QPyServe runtime imports neither DuckDB nor Apache Arrow.
"""

from ._data import DataBridge, DataFilter, DataQuery, DataSort
from ._database import DatabaseSource, db

__all__ = ["DataBridge", "DataFilter", "DataQuery", "DataSort", "DatabaseSource", "db"]

# QPyServe Data Bridge (experimental, introduced in 0.6.0)

**Big data in Python. A real JavaScript frontend. Transfer only the data the
screen needs.** This opt-in experimental feature is available in PyPI QPyServe
0.6.0 and newer.

QPyServe Data Bridge provides a small, controlled query protocol over DuckDB.
It builds read-only, lazy DuckDB relations and pushes column projection,
predicates, sorting, and bounded pagination to the server before converting
results. Results can be ordinary JSON for small tables or a streamed Apache
Arrow IPC response for efficient columnar consumption.

## Install

```bash
python -m pip install "qpyserve[data]==0.6.0"
```

The `data` extra installs DuckDB and PyArrow. Ordinary QPyServe installations
do **not** import or require either package.

## Minimal backend: a Parquet dataset

```python
from fastapi import FastAPI
from qpyserve import run
from qpyserve.data import DataBridge

app = FastAPI()
bridge = DataBridge(app, public=True)  # Public, intentionally, for a demo!
bridge.parquet("pipes", "data/pipes.parquet")

if __name__ == "__main__":
    run(app, frontend="frontend")
```

The file path is configured by the Python developer, not accepted from the
browser. `parquet` resolves local paths relative to the current working
directory when the dataset is registered. DuckDB reads Parquet lazily; the
server does not create a giant Pandas DataFrame simply to expose the data.
Use `DataBridge.relation` when the source is a SQL query, joined tables, or
another DuckDB relation:

```python
bridge.relation(
    "metrics",
    lambda con, request: con.sql(
        "SELECT sensor_id, pressure FROM read_parquet('data/metrics/*.parquet')"
    ),
)
```

DuckDB connections are **per request**, not global. The provider is passed
a fresh connection and the FastAPI `Request`. This enables developers to
apply request-scoped/tenant-scoped restrictions in their own source providers.

## JavaScript/React/Vue client

Data Bridge ships a tiny same-origin JavaScript module with no runtime npm
dependencies. In the browser:

```javascript
import { dataset } from "/api/data/_client.js";

const pipes = dataset("pipes");
const metadata = await pipes.schema(); // names and types, without scanning rows
const page = await pipes.query({
  columns: ["pipe_id", "diameter", "material"],
  filters: [{ column: "diameter", op: "gte", value: 12 }],
  sort: [{ column: "pipe_id", desc: false }],
  limit: 100,
  offset: 0
});

console.log(page.rows, page.has_more);
```

For columnar transfer, install the standard Arrow JS decoder in a Vite app:

```bash
npm install apache-arrow
```

```javascript
import { tableFromIPC } from "apache-arrow";
import { dataset } from "/api/data/_client.js";

const pipes = dataset("pipes");
const bytes = await pipes.arrow({
  columns: ["pipe_id", "diameter"],
  filters: [{ column: "diameter", op: "gte", value: 12 }],
  limit: 2000
});
const table = tableFromIPC(bytes); // Arrow Table; no JSON row decoding
```

The browser still requests **bounded pages**, not an unlimited 100-million-row
transfer. `.arrow()` returns a `Uint8Array` and the standard Arrow JS library
decodes it. It does not automatically render a chart or a map.

Both query methods accept an optional `AbortSignal` as the second argument,
for example `await pipes.query({limit:100}, controller.signal)`.

## HTTP contract

| Endpoint | Result |
| --- | --- |
| `GET /api/data/pipes` | Dataset column names/types and query limits |
| `POST /api/data/pipes/query` | JSON page and `has_more` |
| `POST /api/data/pipes/query?format=arrow` | Arrow IPC streaming response |
| `GET /api/data/_client.js` | Public browser client module, no data itself |

A JSON query body can contain:

```json
{
  "columns": ["pipe_id", "diameter"],
  "filters": [
    {"column": "diameter", "op": "gte", "value": 12},
    {"column": "material", "op": "in", "value": ["PVC", "DIP"]}
  ],
  "sort": [{"column": "pipe_id", "desc": true}],
  "limit": 1000,
  "offset": 0
}
```

Supported operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`,
`in`, `not_in`, `is_null`, `is_not_null`. All identifiers must match
registered columns; arbitrary SQL expressions and file paths from JavaScript
are refused. Scalar values are restricted to strings, finite numbers,
booleans and null. Inputs have conservative limits, including at most
20 predicates, at most 100 `IN` values and a default **10,000-row maximum**
per request (configurable up to 100,000). Offset is limited to 1,000,000.

JSON returns `rows`, `limit`, `offset`, `has_more`. The Arrow stream
contains only the requested page and schema; it does not include a count
or `has_more`. Arrow is most useful when consumers work directly with
typed columns; small JSON responses can be simpler or faster.

## Security: explicit by design

No dataset becomes accessible merely because a Python DataFrame or database
exists. A developer must register a name and choose **one of**:

```python
# Public demonstration data:
bridge = DataBridge(app, public=True)

# Protected data: FastAPI dependencies guard both schema and query routes.
from fastapi import Depends
bridge = DataBridge(app, dependencies=[Depends(require_user)])
```

For multitenant data, authentication alone is not enough. **A registered
relation provider must also restrict rows to the authorized tenant.**
Use the passed `Request` and established authorization state. Never let
browser input select an arbitrary file, table, tenant or SQL statement.
Static `_client.js` is publicly readable but contains no data or credentials.

Schema and query responses use `Cache-Control: private, no-store`. The
protocol does not add its own authentication, encryption, secrets, or CORS.

## Limits and performance tradeoffs

- The first implementation uses DuckDB as the analytical engine. Pandas,
  Polars, NumPy, GeoParquet, geospatial server-side aggregation and remote
  object stores are future integrations, not claimed first-release features.
- DuckDB uses lazy relations and can push operations down to compatible
  sources. **Actual predicate pushdown and memory use depend on the query,
  file layout, joins and sort order.** Sorting a very large dataset may
  be expensive even when the response is small.
- Arrow IPC writes record batches (up to 2,048 rows each by default) while
  streaming a bounded page. There is still serialization and browser memory
  allocation; this is **not** a universal zero-copy guarantee.
- Offset pagination may become inefficient for deep pages. Cursor/keyset
  pagination and server-side aggregates are future targets. Do not page
  sequentially through an entire billion-row table in a browser.
- JSON may coerce decimal values or lose 64-bit integer precision in JavaScript;
  prefer Arrow for precise typed analytical columns.
- No automatic query-result caching: data may change between requests.
  Separate requests are not a transactionally consistent snapshot.
- Query cancellation stops the HTTP transfer; it does not currently
  promise that every underlying DuckDB computation is interrupted instantly.
- Security for tenant providers is application-specific. A careless provider
  can disclose data even when HTTP endpoints require authentication.

## Demonstration and testing

Run the [million-row, zero-Node HTML demo](../examples/data-bridge/README.md)
and adjust server-side filters and pagination.

Regression checks require the `data` extra:

```bash
python -m pip install -e ".[data,test]"
python -m pytest -q tests/test_data.py
```

Use the `data-bridge-smoke` CI job for real DuckDB queries, Arrow IPC
roundtrips, injection/authorization tests, and wheel packaging. Before making
performance claims, benchmark realistic Parquet files against JSON and
well-established alternatives with identical query plans and environments.

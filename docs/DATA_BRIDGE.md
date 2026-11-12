# QPyServe Data Bridge (experimental, expanded in 0.7.0)

**Big data in Python. A real JavaScript frontend. Transfer only the data the
screen needs.** This opt-in experimental feature began in 0.6.0; file watching and SQL table/view
sources are available in PyPI QPyServe 0.7.0.

QPyServe Data Bridge provides a small, controlled query protocol over DuckDB.
It builds read-only, lazy DuckDB relations and pushes column projection,
predicates, sorting, and bounded pagination to the server before converting
results. Results can be ordinary JSON for small tables or a streamed Apache
Arrow IPC response for efficient columnar consumption.

## Install

```bash
python -m pip install "qpyserve[data]==0.7.0"
```

The `data` extra installs DuckDB and PyArrow. Ordinary QPyServe installations
do **not** import or require either package.

## Simpler workflow: register a file, subscribe to changes (0.7.0)

The simplest way to use Data Bridge now is to connect a CSV/Parquet file
with a single Python statement and let the browser refresh when it changes.

```python
from fastapi import FastAPI
from qpyserve import run
from qpyserve.data import DataBridge

app = FastAPI()
DataBridge(app, public=True, sources={"pumpage": "data/pumpage.csv"})

if __name__ == "__main__":
    run(app, frontend="frontend")
```

In **plain JavaScript, React or Vue**:

```javascript
import { data } from "/api/data/_client.js";

// onData receives a bounded page: {rows, limit, offset, has_more}.
const stop = data("pumpage").watch(({rows}) => renderDashboard(rows), {
  query: {limit: 500},
  intervalMs: 5000,
  onError: (error) => showError(error.message)
});

// Call stop() when the page, component, or dashboard is destroyed.
```

In React, cleanup can be one effect:

```jsx
import { useEffect, useState } from "react";
import { data } from "/api/data/_client.js";

function Dashboard() {
  const [rows, setRows] = useState([]);

  useEffect(() => data("pumpage").watch(
    page => setRows(page.rows),
    {query: {limit: 200}}
  ), []);

  return <pre>{JSON.stringify(rows, null, 2)}</pre>;
}
```

For one-time reads, call `await data("pumpage").rows({limit: 100})`;
this returns the array of rows directly. The older
`dataset("pumpage").query(...)` interface remains supported.

### What refresh actually does

- For local `.csv`, `.parquet`, and `.pq` files, Data Bridge compares
  file modification time and size via a cheap `GET /api/data/{name}/version`
  request. The token is hashed and does not expose local paths.
- If the file is unchanged, **no data query is run**. When it changes, the
  browser requests a new bounded page and invokes the callback.
- The default check interval is **5 seconds** (minimum 1 second). Polling
  means updates may appear up to one interval late. It is not streaming.
- For custom DuckDB relations, the version is `null` and the watch re-queries
  at each interval. Provide `revision=lambda: your_version_token()` when
  registering the relation to skip unchanged queries.
- The watcher returns an unsubscribe function which aborts active HTTP calls.
  A single watch should feed all charts using the same dataset where possible,
  avoiding duplicate polling for every widget.
- This is **source-change detection**, not automatic ingestion from REST APIs
  or arbitrary databases. Prefer Parquet for large datasets, because CSV
  schema inference and scanning can be substantially more expensive.
- For reliable updates, write the new file fully and **replace it atomically**
  instead of letting readers observe a half-written CSV or Parquet file.
- The existing max query limit applies even to `.rows()` and `.watch()`.
  This is not an unlimited all-rows download, auto chart generator, or
  replacement for backend aggregation.

`public=True` is **only** for public/demo data. Protected dashboards must
use FastAPI authorization dependencies on DataBridge and apply tenant-specific
row filtering in their relation providers.

Run the [simple CSV dashboard demo](../examples/data-watch/README.md) to see
edits to a CSV appear in a running browser automatically.

## SQL databases: SQL Server, PostgreSQL, and MySQL (0.7.0)

QPyServe can register a **database table or view** as a Data Bridge source.
The SQL database does the filtering, sorting, projection, and paging itself.
It does **not** copy the table into DuckDB or the browser.

Install the lightweight database extra and your chosen driver:

```bash
pip install "qpyserve[database]"  # SQLAlchemy
pip install pyodbc               # SQL Server, plus Microsoft ODBC Driver on the host
# or: pip install psycopg[binary] # PostgreSQL
# or: pip install pymysql         # MySQL
```

In server environment variables (never frontend JavaScript), set a
SQLAlchemy connection URL, for example `DWO_DB_URL`. For SQL Server, a
server-admin-configured DSN is one option:

```text
DWO_DB_URL=mssql+pyodbc://@DWO_READONLY_DSN
```

The connection URI depends on the database driver and your authentication.
Use a restricted **read-only account** with permission for only the approved
tables or, preferably, read-only views. Encrypt DB connections in production.

**Backend:**

```python
from fastapi import Depends, FastAPI
from qpyserve.data import DataBridge, db

app = FastAPI()

# For internal/private dashboards, protect every data route:
bridge = DataBridge(
    app,
    dependencies=[Depends(require_user)],
    sources={
        "pumpage": db("dbo.DailyPumpage", url_env="DWO_DB_URL",
                      updated_at="ModifiedAt"),
    },
)
```

`require_user` is your application's existing FastAPI authorization
dependency. It is not supplied automatically by QPyServe. If you do **not**
have a `ModifiedAt` or equivalent column, omit `updated_at`.

**Frontend (same API for files and SQL servers):**

```javascript
import { data } from "/api/data/_client.js";

const stop = data("pumpage").watch(
  ({rows}) => updateDashboard(rows),
  {query: {columns: ["Date", "TotalWP"], limit: 100, sort: [{column: "Date", desc: true}]}}
);
```

The database source is registered server-side once and accessed through
a SQLAlchemy connection pool. Backend queries are generated with bound
parameters, and only registered columns may be filtered or selected.
Arbitrary SQL provided by browser users is never executed.

**Supported first-release scope:** standard SQLAlchemy table/view reflection
and JSON pages using DB-side `WHERE`, `ORDER BY`, `LIMIT/OFFSET` or native
dialect equivalents. Supported driver/dialect combinations depend on
SQLAlchemy and the installed driver. Automated integration coverage uses a
real SQLite database and validates SQL Server SQL compilation; it does **not**
claim a live PostgreSQL, MySQL or SQL Server integration test.

### Database synchronization and performance

- With `updated_at="ModifiedAt"`, a cheap **MAX(ModifiedAt)** query supplies
  the source version. The browser only refetches the bounded data page
  when that maximum value changes. Put an index on this column for efficient
  version checks on large tables.
- This timestamp check **does not catch deletions**, nor updates that do not
  change the maximum timestamp. Use a database-maintained change version,
  CDC/notification, or full polling if stronger freshness is required.
- Without `updated_at`, the browser re-queries a bounded page on every poll.
  Default polling is five seconds per watcher. For busy shared dashboards,
  use a less frequent interval and consider server-side shared caching.
- Database queries stay on the DB server, rather than pulling full tables into
  DuckDB first. That avoids unnecessary data movement, but it also means
  SQL database indexes, query plans, database load, and network latency
  determine the performance.
- For meaningful totals/KPIs over huge tables, use a database view that
  computes the desired aggregation server-side. **Do not sum a bounded page
  and claim it represents the whole table.** A general-purpose aggregation
  API is not yet included.
- Database views are the preferred way to expose an existing custom SQL
  query safely. This initial API intentionally does not let browser clients
  run raw SQL or configure their own table names.
- Authentication dependencies guard the endpoints, but **do not automatically
  apply tenant row-level security**. Expose only approved restricted views
  or use database-enforced row-level security. Do not expose broad tables
  to users with different data access requirements.
- The database adapter currently returns JSON, not Arrow. Files and DuckDB
  relations retain their Arrow support.
- The URI is read lazily from `url_env`. Missing credentials and query failures
  produce generic HTTP 503 errors without disclosing the connection string.

## Ready-made dashboard starter

Install `qpyserve[data]` and generate the Node-free HTML dashboard:

```bash
qpyserve new my-dashboard --template dashboard
cd my-dashboard
python main.py
```

To start with an existing CSV, supply `--data file.csv --public-data`.
This explicit acknowledgement is required because the generated dashboard uses
`DataBridge(app, public=True)`, which is **publicly queryable**. Add FastAPI
authorization before connecting private records. The dashboard's mean/min/max
are computed from the first bounded page (up to 500 rows), and must not be
interpreted as whole-dataset statistics.

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

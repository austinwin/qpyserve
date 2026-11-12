# Changelog

## 0.7.0 — Dashboard starter and simpler Data Bridge (2026-11-12)

### Added
- Node-free dashboard starter using `qpyserve new my-dashboard --template dashboard`;
  includes editable HTML/CSS/JS, synthetic CSV, bounded-page KPIs, metric selector,
  chart, search, preview table, and file-change polling.
- `--data file.csv --public-data` imports a custom CSV with an explicit
  acknowledgement that the generated Data Bridge is public.
- One-line CSV/Parquet registration, `/version` endpoint, and browser
  `data(name).rows()` and `data(name).watch()` for bounded data refresh.
- Optional `qpyserve[database]` SQLAlchemy adapter for approved SQL tables/views:
  server-side filters, projection, sorting, pagination and optional
  `updated_at` revision checks. DB credentials remain server-side.
- Dashboard starter, CSV, SQL adapter and wheel resource coverage in tests/CI.

### Compatibility and limitations
- Existing FastAPI + React/Vue/HTML applications retain their interfaces.
- Dashboard example is PUBLIC until the developer adds authorization.
- Dashboard KPIs cover only the loaded page, not all database rows.
- File watching uses polling; SQL adapter offers neither automatic tenant
  row restrictions nor general aggregations, arbitrary SQL or Arrow responses.
- DuckDB, PyArrow and SQLAlchemy remain optional dependencies.

## 0.6.0 — Experimental Data Bridge and Windows developer experience (2026-11-04)

### Added: Data Bridge (experimental)

- Optional `qpyserve[data]` extra adds DuckDB and Apache Arrow; the standard runtime has no new dependencies.
- Opt-in `DataBridge(app, public=True)` or FastAPI-protected dataset registration; lazy Parquet and relation providers.
- Server-side projection, safe allowlisted predicates, ordering and bounded pagination; no arbitrary SQL from browser requests.
- JSON pages or streamed Arrow IPC record batches; standalone same-origin JS client for plain HTML, React and Vue.
- Per-request DuckDB connections, cache-sensitive headers, and explicit controls against unintentional public exposure.
- Million-row HTML demo and integration checks for query results, authorization, SQL injection safety, Arrow roundtrips and wheel contents.
- Data Bridge is included in 0.6.0 but remains opt-in and experimental. Install `qpyserve[data]` to use DuckDB and Arrow. See [Data Bridge documentation](docs/DATA_BRIDGE.md).

### Fixed: Windows development terminal

- Run supervised Vite and FastAPI processes in the invoking Windows terminal rather than opening separate console windows.
- Preserve inherited Vite and Python stdout/stderr, including Uvicorn logs and tracebacks, while keeping Python reload, Vite HMR, and combined Ctrl+C shutdown.
- Add regression checks for child process-group flags, inherited logging, and real cross-platform runtime integration. Development still uses two loopback listeners behind one browser URL; production already supports one listening port.

### Compatibility and release

- Standard `qpyserve` installations have no new data dependencies. Data Bridge needs explicit dataset registration and public access or FastAPI authorization dependencies.
- Existing FastAPI, React and Vue entry points remain compatible; review the Data Bridge security, pagination and streaming limitations before production use.

## 0.5.0 — Typed API, Ship, and updated React/Vite example (2026-11-04)

### Added: Typed API

- Opt-in `client=` in `run(...)` generates a TypeScript browser client from FastAPI OpenAPI and Pydantic schema definitions; generated types cover JSON request/response models and path, query, and header parameters.
- Generate a client with `qpyserve api [directory] --app main:app`; use `--check --json` to fail CI when the generated file is stale.
- Regenerate on Python backend restart during development, or before `--build` for Vite frontends. Generated output is deterministic, written atomically, and refuses to overwrite hand-written files.
- `QPyServeApiError` exposes the HTTP status, operation ID, and optional Trace ID. Unsupported operation types (multipart, streaming/binary, non-JSON responses, cookie parameters, external references) appear in the skip report.

### Added: Ship

- `qpyserve ship` generates a reviewable Dockerfile, credential-aware `.dockerignore`, `docker-start.py`, and `render.yaml` for HTML, React, Vue, or other Vite projects.
- Multi-stage Vite builds support npm, pnpm, Yarn, and Bun. The production Python server respects the hosting provider's `PORT`.
- The generator is non-destructive and exposes `--app`, `--name`, and `--json` options for custom projects and AI-assisted workflows.
- Docker-based CI verifies a built React frontend, FastAPI routes, health endpoint, and disabled production Trace.

### Improved: Trace and tooling

- Trace records OpenAPI operation IDs and safe project-relative Python handler references, linking them to browser errors through the existing validated request ID.
- Added TypeScript compilation and actual mocked-fetch checks for generated API contracts, including invalid-argument rejection, correct encoding, and correlated HTTP failures.
- Updated the React example to React 19.3.1, React DOM 19.3.1, Vite 8.3.5, and `@vitejs/plugin-react` 6.1.2 as one compatibility-tested upgrade.
- Upgraded GitHub Actions `checkout`, `setup-python`, `upload-artifact`, and `download-artifact` dependencies.

### Compatibility and limits

- Existing `run(app, frontend=...)` apps work without typed client generation; `client=` remains opt-in. No new runtime Python dependencies.
- Generated TypeScript is for Vite frontends, not Node-free plain HTML sites. Types do not replace FastAPI runtime validation or authentication.
- `qpyserve ship` prepares deployment files but does not deploy, create an account, configure secrets, or provide persistent storage. The generated Render free plan is intended for evaluation.
- Trace remains local, development-only, in-memory and bounded. It does not collect request/response bodies, cookies, authorization headers, query strings, or absolute filesystem paths.
- The copied report format remains `qpyserve-trace-v2`. Reports still require developer review before sharing.

### Try 0.5.0

```bash
python -m pip install --upgrade qpyserve==0.5.0
qpyserve new demo --template react
cd demo
qpyserve api --app main:app
qpyserve ship
```

See the [README](README.md), [Typed API guide](docs/TYPED_API.md), [Trace guide](docs/TRACE.md) and [Ship guide](docs/SHIP.md).

## 0.4.0 — Trace correlation and runtime reliability

### Added
- **Full-stack diagnostic correlation:** same-origin `fetch` and XMLHttpRequest
  calls (including clients that use XHR, such as Axios) carry a validated
  development trace ID to their FastAPI request. The same ID connects a failed
  browser request with a backend status, route template, duration, and, when
  available, an exception type and project-relative Python source location.
- **Actionable failure categories:** Python exceptions, HTTP 5xx/4xx, rate
  limits (429), access denials (401/403), missing routes (404), and network
  errors are labeled separately. Categories describe observed symptoms, not
  automatically determined causes.
- **Structured AI report v2:** the Trace panel exports a redacted JSON report
  with a summary, correlated browser failures, recent backend failures, and
  relevant request metadata.
- **Process supervision:** in Vite development, QPyServe detects unexpected
  exits and stops both FastAPI and Vite process trees.
- **Windows Python reload:** a lightweight Python-file watcher restarts only
  FastAPI, avoiding Windows Uvicorn console-signal issues. Linux/macOS retain
  Uvicorn's native Python reloader; Vite continues to handle frontend HMR.
- Cross-platform integration tests exercising a generated React app, the
  real Vite-to-FastAPI proxy, Python reload, Trace, and clean shutdown.

### Changed
- The Trace report format is now `qpyserve-trace-v2`. Consumers parsing copied
  Trace reports should update accordingly; the app's public `run(...)` API is unchanged.
- Browser report paths are reduced to configured API prefixes with redacted
  path parameters. The backend stores route *templates*, not raw URL paths.
- Added browser-side correlation/privacy tests and platform-specific runtime
  regression tests. No new runtime dependencies.

### Important limitations
Trace is **development-only**, in memory and bounded; it is not an APM
service. It does not automatically trace database queries, outbound HTTP
clients, or distributed workers. It does not collect request or response
bodies, query strings, cookies, or authorization headers. A report may still
contain project details: inspect it before sending it to anyone.

### Try the release
See [the interactive Trace example](examples/trace-demo/README.md) for
successful calls, a 429, a 503, a Python exception, and an XHR request.
See [Trace documentation](docs/TRACE.md) for correlation and privacy.

## 0.3.0 — Development Trace
- Added a local browser Trace panel with FastAPI request status/timing,
  browser `fetch` failures, JavaScript errors, and a copyable diagnostic report.
- Trace is disabled in production.

## 0.2.0 — Project starters
- Added `qpyserve new` for plain HTML, React and Vue.
- Added `qpyserve doctor --json` for machine-readable setup diagnostics.

## 0.1.x — Initial runtime
- One-command FastAPI + frontend development and production static serving.
- Vite API/WebSocket proxy, static asset protections, caching, and release CI.

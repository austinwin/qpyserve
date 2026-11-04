# Changelog

Changes are grouped by package version. QPyServe follows an early-alpha release cycle.

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

# QPyServe Trace

QPyServe Trace is a **local, development-only** browser panel for FastAPI
applications using plain HTML/JavaScript or Vite-based React/Vue. Trace first
appeared in 0.3.0; **0.4.0** adds browser-to-backend correlation, better
failure categorization, redacted reports, and cross-platform runtime checks.
**0.5.0** additionally records the matched OpenAPI operation ID and a safe,
project-relative Python endpoint handler reference (when available).

## Get started

```bash
python -m pip install --upgrade "qpyserve>=0.5.0"
git clone https://github.com/austinwin/qpyserve.git
cd qpyserve/examples/trace-demo
python main.py
```

Open http://localhost:1111, click **503 Failed fetch** and **500 Python
exception**, then open **Trace** in the bottom-right corner (or press
**Alt+Shift+T**). Select **Refresh**, then **Copy AI report**. The report is
structured JSON that can be pasted into your preferred development assistant.

For full scenario instructions, see the
[interactive example](../examples/trace-demo/README.md).

## How browser and backend events connect

1. The local browser wrapper assigns a validated `x-qpyserve-trace-id` to
   **same-origin API** `fetch` or XMLHttpRequest requests (including
   XHR-based clients such as Axios).
2. FastAPI records a bounded request entry with the ID, HTTP method/status,
   **route template**, request duration, and observed failure category.
   In 0.5.0 it can also include `operation_id` and `endpoint_source`
   (`file.py:line`) for the matched FastAPI handler.
   Unhandled exceptions include their **type** and a project-relative
   `.py:line` reference when available. Exception messages are omitted.
3. The Trace panel joins the failed browser request with its backend entry,
   or retains an unpaired browser network error if no backend response arrived.
4. **Copy AI report** produces `qpyserve-trace-v2` JSON: a summary, recent
   backend failures, correlated browser events, and a bounded recent request
   history. It does not attempt to infer the underlying root cause.

An example of *illustrative* JSON fields (not a live recording):

```json
{
  "format": "qpyserve-trace-v2",
  "summary": {"backend_requests": 2, "backend_failures": 1,
              "browser_events": 1, "correlated_events": 1},
  "backend_failures": [
    {"id": "0123456789abcdef", "method": "GET",
     "route": "/api/failure", "status": 503, "category": "server_error"}
  ],
  "browser_events": [
    {"kind": "HTTP", "trace_id": "0123456789abcdef",
     "path": "/api/[redacted]", "status": 503,
     "backend": {"route": "/api/failure", "status": 503,
                 "category": "server_error", "source": null}}
  ]
}
```

These fields are abbreviated and illustrative; actual operation IDs and source
locations depend on the app. Real entries also include timestamps and other
permitted metadata. This example cannot establish the cause of the HTTP 503.

### Failure categories

| Category | Observed condition |
| --- | --- |
| `python_exception` | Unhandled Python exception |
| `server_error` | HTTP 5xx without an observed unhandled exception |
| `rate_limited` | HTTP 429 |
| `access_denied` | HTTP 401/403 |
| `not_found` | HTTP 404 |
| `client_error` | Other HTTP 4xx |
| `network_error` | Browser network failure, status 0, or rejected request |
| `ok` | Response below 400 |

These are **classifications, not automated root-cause diagnoses**.

## Local configuration and privacy

Trace starts automatically with `python main.py` in development.
Opt out with `run(app, frontend="frontend", trace=False)`. Production mode
disables Trace and does not include its browser assets.

- The backend holds **at most 100 recent request entries per process**; the
  browser holds **at most 50 recent events per tab**. No persistent telemetry,
  database, cloud account, or external reporting service is used.
- QPyServe does **not** record request/response bodies, query strings,
  cookies, authorization headers, client IP addresses, or absolute
  filesystem paths. The browser does not instrument cross-origin requests.
- Backend paths are **FastAPI route templates**; browser request paths are
  reduced to configured prefixes, with remaining path segments replaced by
  `[redacted]`.
- Project-relative source filenames and route templates can still reveal
  context. **Review reports before sharing them.**
- Browser error messages are omitted from export. A restrictive Content
  Security Policy might require permitting the same-origin Trace script
  and local panel styles.

The local endpoints are `/__qpyserve/trace` for backend snapshots and
`/__qpyserve/trace.js` for the browser client. They must **never be
exposed on an untrusted network**. This is not an authentication mechanism or
a security audit.

Trace currently does **not** automatically instrument SQL, outbound HTTPX,
Redis, or distributed requests. Use dedicated instrumentation (such as
OpenTelemetry) when those details are necessary.

## Development-server reliability (0.4.0+)

For Vite frontends, QPyServe supervises the frontend and FastAPI child
processes. If either exits unexpectedly, the launcher stops both trees and
reports the failed component. Python changes reload the backend without
restarting Vite: **Uvicorn native reload on Linux/macOS** and a small
Python-file watcher on **Windows** (to avoid Windows console signal issues).
Frontend changes continue to use Vite HMR.

Cross-platform CI exercises a generated React app through the live proxy,
checks Trace response metadata, edits a Python endpoint to confirm reload,
then verifies both server ports are released after shutdown. These are
development checks, not a guarantee of production process supervision.

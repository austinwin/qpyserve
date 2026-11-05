# QPyServe

[![PyPI](https://img.shields.io/pypi/v/qpyserve)](https://pypi.org/project/qpyserve/)
[![CI](https://github.com/austinwin/qpyserve/actions/workflows/ci.yml/badge.svg)](https://github.com/austinwin/qpyserve/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**One Python command. A real JavaScript frontend. A real FastAPI backend. One origin.**

QPyServe runs ordinary [FastAPI](https://fastapi.tiangolo.com/) applications with plain HTML/JavaScript, React, Vue, or other [Vite](https://vite.dev/)-based frontends. It keeps your frontend and backend as normal source files; it does **not** replace either framework.

**New in 0.5.0:** Generate a typed TypeScript client from FastAPI/Pydantic (**API**), correlate browser failures with backend handlers (**Trace**), and prepare a Docker/Render deployment (**Ship**). See the [0.5.0 changelog](https://github.com/austinwin/qpyserve/blob/v0.5.0/CHANGELOG.md), [Typed API guide](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/TYPED_API.md), and [Ship guide](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/SHIP.md).

## Quick start

Install Python 3.10+ and QPyServe:

```bash
python -m pip install --upgrade qpyserve
qpyserve new hello
cd hello
python main.py
```

Open **http://localhost:1111**. The frontend, `/api/hello`, and FastAPI's `/docs` share a browser origin. **Plain HTML needs no Node.js.**

For React or Vue:

```bash
qpyserve new hello-react --template react
# Or: qpyserve new hello-vue --template vue
cd hello-react
python main.py
```

React and Vue require Node.js or a compatible JavaScript runtime/package manager. QPyServe installs **project** dependencies when missing and starts Vite with hot-module replacement (HMR). It does not install Node.js itself.

**One development terminal and URL:** Vite and FastAPI run as supervised child processes and print their normal stdout/stderr (including Python logs, tracebacks, and Vite updates) in the terminal where you ran `python main.py`; on Windows they do not open separate console windows. Open only `http://localhost:1111`. Internally, Vite listens on loopback port 1111 and proxies API requests to FastAPI on loopback port 1112; both ports are local-only in development. Press Ctrl+C in the parent terminal to stop both processes. This does not combine them into one process or provide interactive Python step-through debugging automatically; attach your IDE debugger to the backend when needed. For **one listening port**, build and run in production mode with `python main.py --prod --build`.

## Integrate an existing FastAPI app

```python
from fastapi import FastAPI
from qpyserve import run

app = FastAPI()

@app.get("/api/hello")
def hello():
    return {"message": "Hello from Python"}

if __name__ == "__main__":
    run(app, frontend="frontend", port=1111)
```

Keep `frontend/` as normal HTML/JS or a Vite project. Call `fetch("/api/hello")` from the browser without adding a development CORS workaround.

| Command | Purpose |
| --- | --- |
| `python main.py` | Start development with Python reload and Vite HMR |
| `python main.py --build` | Build the Vite frontend and exit |
| `python main.py --prod` | Serve built frontend assets and FastAPI on one port |
| `python main.py --prod --build` | Build and start in production mode |
| `qpyserve new myapp --template react` | Scaffold an app (also supports `html` and `vue`) |
| `qpyserve doctor --json` | Check prerequisites without executing app code |
| `qpyserve api [--check] [--json]` | Generate typed TypeScript or detect schema drift |
| `qpyserve ship [--json]` | Prepare Docker/Render deployment files; **does not deploy** |

## API: typed Python-to-TypeScript contracts

**Opt in** when using Vite/React/Vue. Add `client=` to the existing `run(...)` call:

```python
run(app, frontend="frontend", client="frontend/src/qpyserve-api.ts")
```

QPyServe generates `frontend/src/qpyserve-api.ts` from your FastAPI OpenAPI schema **before Vite builds** and again when Python changes restart the development backend. For example, define a typed endpoint:

```python
from pydantic import BaseModel

class Sensor(BaseModel):
    sensor_id: int
    pressure: float

@app.get("/api/sensors/{sensor_id}", response_model=Sensor, operation_id="getSensor")
def get_sensor(sensor_id: int):
    return Sensor(sensor_id=sensor_id, pressure=42.5)
```

Then in TypeScript:

```ts
import { api } from "./qpyserve-api";

const sensor = await api.getSensor({ path: { sensor_id: 12 } });
console.log(sensor.pressure); // Typed as number
```

Or generate explicitly:

```bash
qpyserve api --app main:app
qpyserve api --check --json  # Non-writing CI/AI check; exit 1 on drift
```

Generated files are replaced only when marked as QPyServe-generated; manually authored files are protected. The CLI `api` command **imports and executes trusted project code** to obtain the schema, unlike `doctor`. JSON request/response contracts are supported; unsupported multipart, streaming, cookie and non-JSON operations are reported as skipped, not silently typed incorrectly. Types are compile-time contracts, not runtime validation.

[Full Typed API documentation](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/TYPED_API.md)

## Trace: debug frontend and backend together

Run `python main.py`, then click **Trace** at the bottom right of the frontend (or press **Alt+Shift+T**). It captures bounded local development metadata for FastAPI requests, same-origin `fetch`/XHR failures, and JavaScript errors. Select **Copy AI report** for structured, redacted JSON.

When a generated API call fails, the report can connect the browser request ID to the FastAPI HTTP status, operation ID, route template, elapsed time and a **project-relative Python handler location** when available. For unhandled exceptions it can also include the exception type and a safe project-relative source reference.

**Trace is development-only and is disabled in production.** It does not store bodies, cookies, authorization headers, query strings, or absolute filesystem paths. It is not production monitoring or automatic root-cause analysis. Review copied reports before sharing. Disable locally using `run(app, trace=False)`.

[Trace guide](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/TRACE.md) · [Interactive failure demo](https://github.com/austinwin/qpyserve/tree/v0.5.0/examples/trace-demo/README.md)

## Ship: prepare a deployable app

```bash
qpyserve ship
# Or: qpyserve ship --app main:app --name my-app --json
docker build -t my-app .
docker run --rm -p 10000:10000 my-app
```

`ship` generates editable `Dockerfile`, `.dockerignore`, `docker-start.py`, and `render.yaml` files. It handles a Vite build in a Docker build stage, runs Python in the final image, and respects the hosting provider's `PORT`. It supports plain HTML and Vite frontends using npm, pnpm, Yarn or Bun.

**Ship does not deploy, create accounts, push code, or provide persistent storage.** Review the files, build locally, push to GitHub, and create a Render Blueprint from `render.yaml` if you choose Render. The generated free plan is for previews: free services sleep and have ephemeral storage. For production, add authentication, HTTPS, monitoring, durable storage, and an appropriate paid service plan as needed.

[Ship and deployment guide](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/SHIP.md)

## Experimental: Data Bridge (not in PyPI 0.5.0)

**Python for big data. JavaScript for the interface.** The development branch
now includes an optional lazy-data bridge built on DuckDB and Apache Arrow.
Python registers a Parquet dataset once; React, Vue, or plain HTML requests
only selected columns, server-side filters, sort order and bounded pages.
An Arrow IPC stream avoids JSON row conversion for analytical clients.

```python
from qpyserve.data import DataBridge

bridge = DataBridge(app, public=True)  # Public data only!
bridge.parquet("pipes", "data/pipes.parquet")
```

```js
import { dataset } from "/api/data/_client.js";
const page = await dataset("pipes").query({ limit: 100, columns: ["pipe_id", "diameter"] });
```

Install from GitHub main with the optional `[data]` extra to try this unreleased
feature. **Data Bridge deliberately requires explicit public access or FastAPI
authorization dependencies**; it never exposes local tables by default.

[Data Bridge design, examples and limitations](https://github.com/austinwin/qpyserve/blob/main/docs/DATA_BRIDGE.md)
· [Live million-row local demo](https://github.com/austinwin/qpyserve/tree/main/examples/data-bridge)

## Production and safety

Build the frontend during CI/CD with `python main.py --build` and serve prebuilt assets using `python main.py --prod`. Node.js is not required in the production runtime for built Vite sites. Plain HTML needs no build.

```python
run(
    app,
    frontend="frontend",
    port=1111,
    host="127.0.0.1",
    workers=1,             # Multiple workers: production only
    api_paths=["/ws"],     # Extra API/WebSocket proxy prefixes
    dist="dist",           # Vite output folder
    app_import="main:app", # For nonstandard Python entry points
    client=None,           # Optional typed client generation (Vite)
    trace=False,           # Optional: disable development Trace
)
```

Development mode binds to the local loopback interface; **never publish a Vite development server**. Production deployments need appropriate HTTPS termination, authentication, authorization, rate limiting, backup, and monitoring. QPyServe does not include a database ORM, authentication system, cloud provisioning, distributed sessions, or load balancing. Static assets under the public frontend directory are readable by clients; never put credentials there.

See [Security](https://github.com/austinwin/qpyserve/blob/v0.5.0/SECURITY.md) and [deployment guidance](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/SHIP.md). Benchmark your own workload; QPyServe makes no unsupported performance or concurrency claims.

## Project resources

- [HTML counter](https://github.com/austinwin/qpyserve/tree/v0.5.0/examples/counter-html) · [React counter](https://github.com/austinwin/qpyserve/tree/v0.5.0/examples/counter-react) · [Trace example](https://github.com/austinwin/qpyserve/tree/v0.5.0/examples/trace-demo)
- [Typed API](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/TYPED_API.md) · [Trace](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/TRACE.md) · [Ship](https://github.com/austinwin/qpyserve/blob/v0.5.0/docs/SHIP.md)
- [Changelog](https://github.com/austinwin/qpyserve/blob/v0.5.0/CHANGELOG.md) · [Contributing](https://github.com/austinwin/qpyserve/blob/v0.5.0/CONTRIBUTING.md) · [Releasing](https://github.com/austinwin/qpyserve/blob/v0.5.0/RELEASING.md) · [Security](https://github.com/austinwin/qpyserve/blob/v0.5.0/SECURITY.md) · [AI agent guide](https://github.com/austinwin/qpyserve/blob/v0.5.0/AGENTS.md)

Run development checks:

```bash
python -m pip install -e '.[dev]'
python -m ruff check src tests examples
python -m pytest -q
python -m build
```

MIT licensed. QPyServe is an early-alpha project with an intentionally thin public API.

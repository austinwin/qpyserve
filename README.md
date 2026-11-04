# QPyServe

[![PyPI](https://img.shields.io/pypi/v/qpyserve)](https://pypi.org/project/qpyserve/)
[![CI](https://github.com/austinwin/qpyserve/actions/workflows/ci.yml/badge.svg)](https://github.com/austinwin/qpyserve/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**One Python command. A real JavaScript frontend. A real FastAPI backend. One origin.**

QPyServe connects normal FastAPI applications with plain HTML/JavaScript, React, Vue, or other Vite frontends. It handles local startup, API proxying, frontend dependencies, and production static assets without replacing either framework.

> **What's new in 0.4.0:** browser-to-FastAPI error correlation, safer AI-ready diagnostic reports, supervised Vite/FastAPI processes, and reliable Python reload on Windows. See the [0.4.0 changelog](https://github.com/austinwin/qpyserve/blob/main/CHANGELOG.md) and [interactive demo](https://github.com/austinwin/qpyserve/tree/main/examples/trace-demo/README.md).

## Create an app

Install once:

```bash
pip install qpyserve
```

Create a working HTML + FastAPI app (no Node.js):

```bash
qpyserve new hello
cd hello
python main.py
```

Open **http://localhost:1111**. Your UI, `/api/hello`, and `/docs` share one browser origin. Click **Call Python API** to see the frontend call your backend.

Prefer React or Vue? Same Python, same command to run:

```bash
qpyserve new hello-react --template react
# Or: qpyserve new hello-vue --template vue
cd hello-react
python main.py
```

React and Vue development require Node.js or a compatible JS runtime/package manager. QPyServe installs missing *project* dependencies automatically and starts Vite with hot-module replacement (HMR). It does **not** silently download Node.js.

### Built for both humans and AI coding agents

Every generated project is ordinary Python and frontend source code. It also includes a short `AGENTS.md` describing the API boundary, security expectations, and build commands. No proprietary UI components or code generation at runtime.

For reproducible startup diagnostics:

```bash
qpyserve doctor
qpyserve doctor --json  # For AI tools and CI
```

`doctor` checks basic development prerequisites and reports actionable errors. It is **not** a security audit or a load test. It never runs arbitrary project code.

## Debug frontend and backend together: QPyServe Trace

Run `python main.py` and click **Trace** in the bottom-right corner of your frontend.
It shows recent FastAPI requests (HTTP status, route template, request ID, timing and
exception type), browser fetch/XHR failures, and JavaScript errors in one development panel.
Trace 0.4 correlates browser failures to backend errors and exports a redacted,
structured report with failure categories and project-relative Python source references.
Select **Copy AI report** to copy structured JSON for debugging with an AI assistant.
Trace works with plain HTML, React and Vue without changing application code.

Trace is enabled automatically in local development; **disabled in production**.
It does not transmit data to external services, record request/response bodies,
capture authorization headers or provide production APM. A copied report should be
reviewed before sharing. To opt out, use `run(app, trace=False)`.

[Trace documentation](https://github.com/austinwin/qpyserve/blob/main/docs/TRACE.md) · [Trace 0.4 example and expected results](https://github.com/austinwin/qpyserve/tree/main/examples/trace-demo/README.md) · [Release changes](https://github.com/austinwin/qpyserve/blob/main/CHANGELOG.md)

### Try the 0.4.0 failure-correlation example

```bash
python -m pip install --upgrade qpyserve
git clone https://github.com/austinwin/qpyserve.git
cd qpyserve/examples/trace-demo
python main.py
```

Open **http://localhost:1111**, click **503 Failed fetch** or
**500 Python exception**, then open **Trace → Copy AI report**. The
`qpyserve-trace-v2` JSON links the browser failure with the matching
FastAPI request ID, category and (for Python exceptions) a safe,
project-relative source location. The demo also includes HTTP 429 and
XMLHttpRequest examples. No JavaScript runtime is needed for this HTML demo.

## Integrate into your existing application

You don't need to use a starter. Keep your existing FastAPI application and frontend folder:

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

The frontend can call `fetch("/api/hello")` without a separate browser origin or development CORS workaround.

| Command | What it does |
| --- | --- |
| `python main.py` | Development mode, including reload/HMR |
| `python main.py --build` | Build a Vite frontend and exit |
| `python main.py --prod` | Serve built assets and FastAPI from one port |
| `python main.py --prod --build` | Build then run production mode |

**Existing projects continue to work.** QPyServe does not change your FastAPI routes or Vue/React component model. It does not require special `npm run dev` scripts or a custom framework router.

See the [HTML counter](https://github.com/austinwin/qpyserve/tree/main/examples/counter-html) and [React counter](https://github.com/austinwin/qpyserve/tree/main/examples/counter-react) for more examples.

## From project to deployable app: QPyServe Ship

After building and testing your application, generate **editable deployment files**:

```bash
qpyserve ship
# Or: qpyserve ship --app main:app --name my-water-map --json
docker build -t my-water-map .
docker run --rm -p 10000:10000 my-water-map
```

Open **http://localhost:10000** to test the container. `ship` generates
`Dockerfile`, `.dockerignore`, `docker-start.py`, and `render.yaml`. It
supports plain HTML or Vite frontends using npm, pnpm, Yarn, or Bun. Vite assets
are built in the Docker build stage; production serves static files and FastAPI
on a single port. `PORT` can be set by the hosting provider.

To publish, review the generated files, commit and push the project to GitHub,
then use **Render Dashboard → New → Blueprint** to connect the repository and
deploy using `render.yaml`. This is deliberately **not** a new hosting
platform, a cloud account connector, or an automatic deploy command.

The generated Render service uses the **free** plan for preview use. Free
services sleep when idle and have ephemeral storage; they are not suitable for
reliable production or persistent local data. Authentication, environment
secrets, external dependencies, DNS and billing remain your responsibility.
Use external durable storage for databases/uploads. Before deploying real
workloads, review `docker-start.py`, requirements, the Docker build logs,
and your API's authorization rules. Existing deployment files are never
overwritten by `ship`. See [Render's free-plan limitations](https://render.com/docs/free).

## Production

Build the frontend during CI/CD with `python main.py --build`. Run `python main.py --prod` with prebuilt assets. Node.js isn't required in the production runtime for static frontends. Plain HTML/JS needs no build.

Place public services behind HTTPS termination, process supervision, and application-specific authentication and rate limiting. QPyServe stays deliberately thin: it does **not** implement an auth system, database ORM, distributed sessions, a load balancer, or deployment infrastructure.

Optional configuration:

```python
run(
    app,
    frontend="frontend",
    port=1111,
    host="127.0.0.1",
    workers=1,             # Production only
    api_paths=["/ws"],     # Additional API/WebSocket proxy prefixes
    dist="dist",           # Vite output directory
    app_import="main:app", # Only for nonstandard Python entry points
    trace=False,           # Optional: disable local development Trace panel
)
```

Development mode binds to loopback only, and Vite development must never be exposed as a public production server. External clients use the same `/api/*` routes as the browser, subject to network and authentication rules. Multi-worker applications must use shared state where appropriate.

### Security boundaries

| Area | Responsibility |
| --- | --- |
| QPyServe | Static file serving, path protection, local Vite proxy, reload/build orchestration |
| FastAPI / your code | Authorization, validation, authentication, CORS, sessions and business logic |
| Deployment platform | HTTPS, monitoring, rate limiting, backups, scaling and load balancing |

QPyServe blocks common private/development files and escaping symlinks when serving static assets, but **anything intentionally placed in a public frontend file can be downloaded**. Never place credentials in the frontend; API routes are public unless explicitly protected. A security review of your application is still necessary. See [SECURITY.md](https://github.com/austinwin/qpyserve/blob/main/SECURITY.md).

## Scope and performance

QPyServe does not claim to be faster than FastAPI or competing frameworks. API and browser performance depend on your application, dependencies, workload, deployment, and caching. It is designed to avoid adding unnecessary abstractions. Benchmark representative workloads before claiming a particular concurrency target.

Supported frontends: plain HTML/JS, React, Vue, and other static Vite projects. Server-rendered Next.js, distributed WebSocket fan-out, and automatic cloud provisioning remain outside scope.

## Contributing

```bash
python -m pip install -e '.[dev]'
python -m ruff check src tests examples
python -m pytest -q
python -m build
```

Read [CONTRIBUTING.md](https://github.com/austinwin/qpyserve/blob/main/CONTRIBUTING.md), [AGENTS.md](https://github.com/austinwin/qpyserve/blob/main/AGENTS.md), [RELEASING.md](https://github.com/austinwin/qpyserve/blob/main/RELEASING.md), and the [changelog](https://github.com/austinwin/qpyserve/blob/main/CHANGELOG.md). MIT-licensed.

### Development runtime reliability (0.4.0)

When using Vite, QPyServe supervises the frontend dev server and the FastAPI
reload process together. If either crashes, it exits with a clear error and
cleans up both process trees. Python edits restart the API (Uvicorn's reloader on Linux/macOS,
QPyServe's lightweight restart watcher on Windows); frontend edits use
Vite HMR. Production process supervision remains the deployment platform's job.

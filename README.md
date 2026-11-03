# QPyServe

[![PyPI](https://img.shields.io/pypi/v/qpyserve)](https://pypi.org/project/qpyserve/)
[![CI](https://github.com/austinwin/qpyserve/actions/workflows/ci.yml/badge.svg)](https://github.com/austinwin/qpyserve/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**FastAPI and a real web frontend, served from one origin with one Python command.**

QPyServe is a small integration layer, not another web framework. Keep your normal FastAPI
routes and your normal HTML/JavaScript, React, Vue, or other Vite frontend. QPyServe handles
development startup, the local API proxy, and serving static assets in production.

> **Status:** Early alpha. See [PyPI](https://pypi.org/project/qpyserve/) for the latest published version.
> No production throughput or security certification is claimed.

## Quick start: plain HTML, no Node.js

Install the published package:

```bash
python -m pip install qpyserve
```

Create two files:

```text
my-app/
├── main.py
└── frontend/
    └── index.html
```

`main.py`:

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

`frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>QPyServe demo</title></head>
  <body>
    <button id="hello">Call Python</button>
    <pre id="result"></pre>
    <script>
      document.querySelector("#hello").addEventListener("click", async () => {
        const response = await fetch("/api/hello");
        if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        document.querySelector("#result").textContent =
          JSON.stringify(await response.json(), null, 2);
      });
    </script>
  </body>
</html>
```

Run the entire application:

```bash
python main.py
```

Open [the frontend](http://localhost:1111/), [the JSON API](http://localhost:1111/api/hello),
or [FastAPI documentation](http://localhost:1111/docs). Plain HTML needs no Node.js.

## React, Vue, and Vite

Use any ordinary Vite project as `frontend/`. Your Python backend stays the same.
QPyServe detects Vite through `package.json`, detects npm/pnpm/Yarn/Bun,
installs missing dependencies, and starts the dev server with API proxying and HMR.
No custom `npm run dev` script is required.

A JavaScript runtime/package manager is still required on the development machine.
QPyServe does **not** silently install Node.js or download runtime binaries.

The browser uses one origin, `http://localhost:1111`. Vite proxies `/api/*`,
`/docs`, and other configured API paths to a loopback FastAPI server at `:1112`.

Examples: [HTML counter](examples/counter-html) and [React counter](examples/counter-react).

## Run, build, deploy

| Command | Purpose |
| --- | --- |
| `python main.py` | Development server with reload / Vite HMR |
| `python main.py --build` | Compile a Vite frontend and exit |
| `python main.py --prod` | Serve prebuilt assets and FastAPI on one port |
| `python main.py --prod --build` | Build once, then serve |

Build static assets in CI and deploy the output with the Python app.
Production does **not** require Node.js if frontend assets are already built.

For external clients, put the app behind an HTTPS reverse proxy or managed load
balancer. QPyServe does not implement authentication, rate limiting, queues,
shared session storage, or production orchestration.

### Optional configuration

```python
run(
    app,
    frontend="frontend",
    port=1111,
    host="127.0.0.1",       # loopback by default
    workers=1,              # production mode only
    api_paths=["/ws"],      # additional API / WebSocket prefixes
    dist="dist",            # Vite output folder
    app_import="main:app",  # only for nonstandard entrypoints
)
```

Development mode binds only to loopback. Use production mode behind TLS when
serving remote users. `api_paths` reserves custom prefixes from SPA fallback
and proxies them to FastAPI during development. It does not create or secure endpoints.

## Security boundaries

- **Frontend:** QPyServe serves known public browser asset types, rejects hidden files,
  source maps, common credentials, and paths or symlinks escaping the static root.
  Its static responses include `X-Content-Type-Options: nosniff`.
- **API:** FastAPI owns authentication, authorization, input validation, CORS, and
  session security. **Your API routes are public unless you protect them.**
- **Infrastructure:** Configure HTTPS, trusted proxy headers, firewall rules,
  rate limits, monitored deployments, and external shared state as appropriate.
- **Secrets:** Keep private data entirely outside the served frontend directory.
  A public `data.json` file remains public even when the file server is secure.

QPyServe does not impose one Content Security Policy on every frontend; configure a
policy matching your app's scripts, maps, fonts, and integrations.
See [SECURITY.md](SECURITY.md) for deployment and vulnerability-reporting guidance.

The counter demos use in-memory state **for illustration only**. Multiple workers
do not share Python globals.

## Who owns what?

| Concern | Owner |
| --- | --- |
| Startup, Vite proxy, static assets and basic reload | QPyServe |
| HTTP/WebSocket APIs, authentication, databases | FastAPI / your app |
| Frontend compilation and HMR | Vite |
| HTTPS, scaling, monitoring, caching, load balancing | Deployment platform |

Next.js SSR, automatic infrastructure provisioning, and distributed WebSocket
fan-out are deliberately outside scope.

## Contributing and verification

```bash
python -m pip install -e '.[dev]'
python -m ruff check src tests examples
python -m pytest -q
python -m build
```

GitHub CI covers Python 3.10, 3.12, 3.13 on Linux, Python 3.12 on Windows,
and a React/Vite startup smoke test.
Read [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md), and
[RELEASING.md](RELEASING.md) for project guidance.

QPyServe is MIT-licensed. It does not accelerate backend queries or guarantee a
specific concurrency level. Benchmark the deployed app before making performance claims.

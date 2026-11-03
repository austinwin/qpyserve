# qpyserve

**FastAPI + any frontend. One Python command. One browser address.**

`qpyserve` is a small runtime bridge, not another backend framework. Keep normal FastAPI routes and write the frontend in HTML/JS or a Vite-based framework such as React/Vue. It starts the right development servers and serves built files in production.

> **Status:** Early alpha. Not yet load-tested or security-audited. Do not confuse multi-worker support with a guarantee of capacity for 1,000 users.

## Installation

```bash
pip install -e .
```

For an app consuming the eventual PyPI release, the goal is `pip install qpyserve`. Vite projects need Node.js/npm for development and builds; plain HTML projects do not.

## Hello world (HTML only)

`main.py`:

```python
from fastapi import FastAPI
from qpyserve import run

app = FastAPI()

@app.get('/api/hello')
def hello():
    return {'message': 'Hello from Python'}

if __name__ == '__main__':
    run(app, frontend='frontend', port=1111)
```

`frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <body>
    <button id="hello">Call Python</button><pre id="result"></pre>
    <script>
      document.querySelector('#hello').onclick = async () => {
        const response = await fetch('/api/hello');
        document.querySelector('#result').textContent =
          JSON.stringify(await response.json());
      };
    </script>
  </body>
</html>
```

Run `python main.py` and visit <http://localhost:1111>. API docs are at `/docs`. Frontend HTML/JS changes auto-refresh in development.

For runnable examples see [`examples/counter-html`](examples/counter-html) and [`examples/counter-react`](examples/counter-react).

## React/Vue via Vite

Create a normal Vite app under `frontend/` with a `package.json` containing `vite` and a `dev` script. Use the exact same `main.py` and `run(...)` call. `python main.py` installs npm dependencies if needed and starts Vite on `:1111` with its `/api` and docs routes proxied to a local FastAPI server on `:1112`. Your existing `vite.config.js`/`.ts` and plugins are retained. React/Vue HMR is native Vite HMR.

During development, the **browser origin** is always `http://localhost:1111`; port 1112 is local-only. External API clients use `http://localhost:1111/api/...` in development or your deployment domain in production. The Vite server is for **trusted local development only** and must not be exposed as a production web server.

## Production

For a Vite app, build it on the build machine first:

```bash
cd frontend && npm install && npm run build && cd ..
python main.py --prod
```

Production runs **FastAPI on port 1111**, serving the compiled `frontend/dist` and normal `/api/*` routes. Node/npm are not required to **run** the production app once the static build exists. For an HTML-only app no build is needed. The built-in `--prod` server is a useful starting point; production deployments should also provide HTTPS termination, process supervision, and appropriate authentication, rate limits, and observability.

Optional parameters:

```python
run(app, frontend='frontend', port=1111, host='127.0.0.1',
    workers=1, dist='dist', app_import='main:app')
```

Use `host='0.0.0.0'` only when intentionally making the service network-accessible. `workers > 1` is for production only and your API should use external shared state (e.g. PostgreSQL/Redis). Import string is automatically inferred for the normal `python main.py` convention; pass `app_import` for nonstandard entry points.

Set `QPYSERVE_MODE=production` instead of `--prod` if desired. FastAPI retains ownership of API routing, OpenAPI, dependencies, security, and middleware. Missing `/api/*` routes return 404 rather than your SPA index.

## Design boundaries

- **qpyserve manages:** process startup, basic development proxy, plain HTML reload, Vite integration, and production static hosting.
- **FastAPI manages:** endpoints, authentication, business rules, database interaction, validation, and API docs.
- **Vite manages:** frontend development, dependency graph, HMR and frontend builds.
- **Your hosting infrastructure manages:** HTTPS, autoscaling, deployment, queues, distributed caches, and disaster recovery.

No proprietary components, generated frontend APIs, database wrapper, or AI runtime. It deliberately keeps application code portable.

## Limitations

- Vite development currently requires **npm** and a conventional `npm run dev` script invoking Vite.
- The auto-configured dev proxy covers `/api`, `/docs`, `/redoc`, `/openapi.json`, and `/__qpyserve`. Add other paths in your Vite config if needed.
- Static site live reload is intended for development; it polls local asset mtimes and injects a small script into HTML responses.
- In-memory counters/sessions are not shared across workers, processes, or servers.
- Full Next.js SSR, distributed WebSocket fan-out, and automatic infrastructure provisioning are outside v0.1 scope.

## Tests

```bash
pip install -e '.[test]'
pytest -q
python -m build
```

MIT License.

# qpyserve

**FastAPI + any frontend. One Python command. One browser address.**

QPyServe is a thin bridge, not a new web framework. Write normal FastAPI endpoints and use plain HTML/JS, React, Vue, or another Vite frontend. QPyServe handles local startup, frontend dependencies, API proxying, hot reload, and static production serving.

> **Status:** Early alpha. Not yet load-tested or security-audited. Multiple workers do not guarantee performance for 1,000 concurrent users.

## Installation

```bash
pip install qpyserve
```

For a source checkout: `python -m pip install -e .` instead. If not yet released to PyPI, install from GitHub: `pip install git+https://github.com/austinwin/qpyserve.git` (requires repository access).

## Hello world: two files

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

```bash
python main.py
```

Open <http://localhost:1111>. `/api/hello` serves the same origin and `/docs` shows FastAPI documentation. No Node.js, package.json, or additional commands are needed for plain HTML. Edit HTML/JS and the development page automatically refreshes.

## React, Vue, or another Vite frontend

Point `frontend='frontend'` to an ordinary Vite project containing `package.json` with `vite` in its dependencies. **The Python code does not change.** Run `python main.py`.

- QPyServe detects npm, pnpm, Yarn, or Bun from `packageManager` / lockfiles (npm is the fallback).
- It installs missing frontend dependencies with the selected package manager, then runs the locally installed Vite. No `npm run dev` script is required.
- Existing `vite.config.js` / `.ts` / `.mjs` and plugins are retained; Vite provides normal HMR.
- Development browser URL stays `http://localhost:1111`. The API runs on loopback `:1112` and is proxied through `:1111`.
- Node.js and the chosen package manager must be installed for Vite projects. QPyServe does **not** silently install Node or fetch arbitrary runtime binaries. It reports what is missing.

See the runnable [HTML counter](examples/counter-html) and [React counter](examples/counter-react).

## Production and builds

| Command | Behavior |
| --- | --- |
| `python main.py` | Start dev server, HMR/reload; install frontend packages if needed |
| `python main.py --build` | Install packages if needed, build frontend, and exit |
| `python main.py --prod` | Serve prebuilt frontend and FastAPI on one port |
| `python main.py --prod --build` | Build frontend first, then serve it in production mode |

Plain HTML needs no build. For Vite sites, build once in CI/CD using `--build`; production machines only need Python and the built static files. Avoid building on every production restart.

**Production deployment:** Put an HTTPS reverse proxy or managed load balancer in front, use process supervision, secure the API using ordinary FastAPI dependencies/middleware, and add shared storage/caching as needed. QPyServe does not provide authentication, rate limiting, distributed state, or production infrastructure on its own.

## Advanced options (optional)

```python
run(
    app,
    frontend='frontend',
    port=1111,
    host='127.0.0.1',
    workers=1,
    api_paths=['/ws', '/custom'],  # /api and FastAPI docs are always included
    dist='dist',
    app_import='main:app',  # only needed for nonstandard entrypoints
)
```

`api_paths` explicitly adds proxy prefixes for custom HTTP routes or WebSockets during Vite development and prevents those prefixes from falling back to the SPA HTML in production. It does not create or authenticate endpoints. Don't use a broad prefix such as `/` because it would consume frontend routes.

Bind `host='0.0.0.0'` only when you intentionally want to expose the service over a network; never expose the Vite development server to the public internet. `workers > 1` requires production mode and a shared state store for data that must persist across processes. The normal FastAPI OpenAPI/docs and external API clients keep working. Custom Vite proxy/SSR settings remain your frontend's responsibility when your app needs unusual behavior.

## Scope and boundaries

- **QPyServe:** startup/orchestration, dependency detection, Vite development proxy, SPA/static file serving, basic dev reload.
- **FastAPI:** APIs, authentication, security, WebSockets, validation, database code, dependency injection.
- **Vite:** React/Vue/JS build, HMR, frontend plugins.
- **Deployment platform:** HTTPS, worker replicas, monitoring, database, caches, queues, backups.

Vite builds are static SPAs; Next.js server-side rendering, distributed WebSocket fan-out, automatic Kubernetes provisioning, and shared-memory magic are not provided. The HTML file server excludes hidden files, package manager manifests, and Python sources; don't put secrets in a public frontend directory.

## Contributing and verification

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python -m build
```

Check [AGENTS.md](AGENTS.md) for AI-assisted contributions and [RELEASING.md](RELEASING.md) for PyPI publishing. MIT License.

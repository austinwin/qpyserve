# My QPyServe app

One Python backend and a real web frontend, on the same origin.

## Start

```bash
python main.py
```

Open <http://localhost:1111>. The API is available at <http://localhost:1111/api/hello> and Swagger documentation at <http://localhost:1111/docs>.

Vite-based frontends require Node.js/npm (or your selected supported package manager) installed; QPyServe installs local JavaScript dependencies and starts Vite for you. Plain HTML needs only Python.

## Production

For Vite, first run `python main.py --build` on a build machine; then run `python main.py --prod` to serve built assets. A static HTML frontend needs no build.

API endpoints are publicly reachable unless you secure them using FastAPI dependencies/middleware. Do not commit secrets or store them under the frontend folder.

## Typed API (Vite projects, QPyServe 0.5.0+)

To generate a TypeScript client from your FastAPI routes, change the `run(...)`
call in `main.py` to include `client="frontend/src/qpyserve-api.ts"`.
QPyServe regenerates it on Python reload. Or use `qpyserve api --check --json`
to detect contract drift in CI. Plain HTML can continue using `fetch` directly.

## Deployment preparation

Run `qpyserve ship` to generate Docker and Render Blueprint configuration.
Review and test these files before deployment. This does not publish your app
or provide durable storage. See the
[Ship guide](https://github.com/austinwin/qpyserve/blob/main/docs/SHIP.md).

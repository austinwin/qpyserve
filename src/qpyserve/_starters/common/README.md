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

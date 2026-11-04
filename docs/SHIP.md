# QPyServe Ship: prepare your app for deployment

Available starting with **QPyServe 0.5.0**. `ship` prepares ordinary, editable deployment files for a full-stack FastAPI + HTML/React/Vue application. It is **not** a cloud hosting service and does **not** deploy the application.

## Generate the deployment files

From an existing QPyServe project:

```bash
python -m pip install --upgrade "qpyserve>=0.5,<1"
qpyserve doctor
qpyserve ship
# For a nonstandard app:
# qpyserve ship --app server:app --name water-dashboard --json
```

The command requires a project with a Python application module and `frontend/index.html`. It writes these files only if none already exists:

| File | Purpose |
| --- | --- |
| `Dockerfile` | Builds the frontend (Vite when applicable), installs Python requirements, and launches a one-port production server |
| `.dockerignore` | Excludes common local caches, build output, and credential files from the Docker build context |
| `docker-start.py` | Imports the FastAPI app and launches QPyServe in production mode using `PORT` (default 10000) |
| `render.yaml` | Example Render Blueprint using Docker and a `/__qpyserve/health` check |

If one of these files is already present, generation stops instead of overwriting it. The files are **owned by your app** after generation; review and customize them as needed.

## Validate locally before publishing

```bash
docker build -t my-qpyserve-app .
docker run --rm -p 10000:10000 my-qpyserve-app
```

Visit `http://localhost:10000`, test a real `/api/*` endpoint, and confirm `/__qpyserve/health` returns `{"status":"ok"}`. Production mode serves static assets and FastAPI through the same port. Development-only Trace must not be available in the running image.

**If your application needs extra Python dependencies**, declare them in a `requirements.txt` or an installable project `pyproject.toml`. The generated Dockerfile installs these when present; verify the full install in your own build. Do not put passwords or tokens in the frontend bundle, source, or Dockerfile.

## Deploy to Render using your own account

1. Review the generated Dockerfile, `.dockerignore`, `docker-start.py`, and `render.yaml`. Check requirements, application import path, storage, authentication, and secrets.
2. Commit and push the project to a GitHub repository.
3. In the Render dashboard, create a **Blueprint**, connect that repository, and review the proposed service and plan before confirming deployment.
4. Configure application secrets using Render's environment variables and use an external durable database/object store for any persistent state.
5. Test the assigned public URL (frontend and protected backend API), inspect logs, configure HTTPS/domain settings, and monitor the service.

The example `render.yaml` selects Render's **free** plan. Free service availability and terms may change; free instances can sleep when idle, have ephemeral disks, and are unsuitable for uptime-critical applications. Check [Render free limitations](https://render.com/docs/free) and [Blueprint documentation](https://render.com/docs/infrastructure-as-code) before choosing a plan.

## Security and operational checklist

- **Authentication/authorization:** protect every sensitive API route; public `/api/*` paths are not protected by QPyServe automatically.
- **Secrets:** pass environment variables through the hosting provider; verify `.dockerignore` actually excludes your project's sensitive files.
- **Persistence:** do not use container-local files as durable storage. Multiple instances require shared state.
- **Production network:** put the app behind managed HTTPS, enable appropriate rate limits, and use deployment-level process supervision.
- **Frontends:** static files shipped in the browser are public. Generated TypeScript API clients contain route definitions, not authorization.
- **Verification:** test the exact container, including frontend assets, API health, dependencies, configuration, failure/restart behavior and logs.

## Supported cases and boundaries

- Plain HTML: no Node.js or frontend build step required.
- Vite/React/Vue: the build stage uses the detected npm, pnpm, Yarn, or Bun configuration; the final Python container does not need the JS toolchain.
- Custom build outputs and multi-service topologies may need manual Dockerfile modifications.
- `ship --json` reports files created, frontend type, warnings, and `"deployed": false`.
- `ship` does not push to GitHub, create Render services, configure domains/secrets, guarantee security, or publish to PyPI.

For local development and generated API contracts, see the [README](../README.md) and [Typed API](TYPED_API.md).

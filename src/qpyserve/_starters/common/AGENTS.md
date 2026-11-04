# AI development notes

- Keep backend routes, business rules, and secret-bearing integrations in normal FastAPI Python code.
- Keep UI state and browser interactions in `frontend/`; call Python using relative `/api/...` URLs.
- QPyServe owns dev startup, proxying and static serving. Do not add a second public port, CORS workaround, or duplicate build server for normal usage.
- Keep credentials outside `frontend/`; frontend files are public. Never put API keys in JavaScript.
- API endpoints are **not** authenticated by default. Use FastAPI security dependencies where appropriate; never claim this app is secure without checking them.
- `python main.py` runs development; `python main.py --build` builds Vite; `python main.py --prod` serves built assets.
- Preserve existing API contracts; add focused tests when changing behavior. In-memory state is not shared between workers.

- QPyServe 0.5.0 can generate a typed TypeScript client for Vite projects via
  `run(..., client="frontend/src/qpyserve-api.ts")`. Do not hand-edit generated
  code; regenerate from FastAPI/Pydantic and check `qpyserve api --check`.
- `qpyserve ship` creates editable deployment files but does not deploy.
  Keep secrets out of the Docker build context and protect public APIs.

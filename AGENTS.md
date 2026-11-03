# AI developer guide

QPyServe is an intentionally thin integration layer. Maintain the smallest public API that solves the actual user problem.

- Do not replace FastAPI or implement a custom routing/authentication layer.
- Preserve public `run(app, frontend='frontend', port=1111)` compatibility.
- Keep frontend code independent. Do not generate React/Vue components from Python.
- Local HTML apps must work without Node.js; Vite frontends use their own JS toolchain.
- `python main.py` should do everything needed for local development (apart from a one-time installation of the Python package and system-level JS runtime).
- Keep `--prod` free of Node dependencies if built files exist; `--build` is opt-in.
- Default network binding is loopback, and Vite is not a public production server.
- Custom API prefixes must be handled consistently in Vite proxy and static SPA fallback.
- Never serve frontend `.env`, package manifests, or Python sources as public assets.
- Run Python tests on Linux and Windows in CI when changing subprocess logic; test real React/Vite launch when possible.
- Keep in-memory state explicitly local; scaling requires shared storage and representative load testing.
- Update tests and README for any public behavior change. Avoid new dependencies without measurable benefit.

- Static asset routes are public: validate requested and resolved paths; never serve arbitrary project files.
- Development servers must remain bound to loopback; production API authentication belongs to FastAPI.
- Run Ruff lint checks and regression tests for security, process, and routing changes.
- Never treat passing tests as proof of security certification or 1,000-user performance.

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

- Keep the public `qpyserve new` command template-based and non-destructive.
- Keep project templates in `src/qpyserve/_starters/` and include them in built distributions.
- The `qpyserve doctor --json` output must remain machine-readable and must never execute user code.
- Avoid new runtime dependencies, embedded AI services, custom UI components, or a proprietary backend router.


- QPyServe Trace must remain development-only, bounded and in-memory. Never store request bodies, cookies, authorization headers or query strings.
- Keep the trace client framework-independent and avoid adding browser build dependencies.
- Add regression tests when changing trace injection, the Vite proxy or production defaults.

- `qpyserve ship` must never overwrite a user's deployment files, access credentials, or claim to have deployed anything.
- Generated containers must run in production mode, bind to 0.0.0.0, honor `PORT`, and exclude local secrets/build artifacts from Docker context.
- Preserve React/Vue/HTML starter compatibility; generated deployment assets should be ordinary editable files.

- Typed API generation is opt-in and uses FastAPI OpenAPI only; never duplicate the FastAPI router or Pydantic validation system.
- Generate only under frontend/, protect manually written files and symlinks, and do not rewrite identical generated files.
- Unsupported non-JSON, cookie and streaming operations must be reported; never generate incorrect client types.
- Generated browser code uses same-origin native fetch so dev Trace correlation works without extra telemetry.
- Generated TS must be verified with TypeScript type checking and live API/trace tests; production must not regenerate client source.

- Data Bridge is opt-in and must never import DuckDB/Arrow for ordinary `run(...)` applications.
- Keep Data Bridge registration explicitly public or protected by FastAPI dependencies; never accept browser SQL or file paths.
- Query execution must project/filter/page lazily on the backend with bounded limits. Avoid silently collecting an entire large dataset in Python or JavaScript.
- Use per-request DuckDB connections and test Arrow IPC wire compatibility, tenant filtering and injection resistance.
- Never claim zero-copy, effortless billion-row transfer or speedups without a representative benchmark.

- Data Bridge's first-run API is `DataBridge(app, public=True, sources={"name": "data/file.csv"})`.
  Keep source paths server-owned; do not make public access the default.
- Browser `data(name).watch(...)` must check a cheap revision token before
  re-querying file data, skip unchanged file versions, and abort requests on cleanup.
  Non-versioned relation providers are intentionally polled each interval.
- Preserve API compatibility with `DataBridge.relation`, `.parquet`, and
  `dataset(name).query(...)`; never fetch entire large datasets by default.

- Server-side SQL database sources are registered with `db(table, url_env=...)`;
  use SQLAlchemy's bound parameters and dialect-specific pagination. Never
  interpolate browser filter values, SQL fragments, or table names.
- Database connections and credentials stay server-side. Prefer a database
  read-only user restricted to approved views; FastAPI auth alone does not
  provide per-tenant row filtering.
- `updated_at` uses MAX(timestamp), which may miss deletes or unchanged-max
  updates; don't claim CDC or true real-time semantics.
- Keep `qpyserve[database]` optional, and don't import SQLAlchemy in ordinary
  QPyServe or file-only Data Bridge startup paths.

# AI developer guide

qpyserve is an intentionally thin integration layer. Keep it small and boring.

- Do not replace FastAPI or implement a custom routing/authentication layer.
- Preserve public `run(app, frontend='frontend', port=1111)` compatibility.
- Keep frontend code independent and do not generate React/Vue components from Python.
- Only Vite development requires Node; production serves prebuilt static files.
- Vite proxies `/api` in development; FastAPI owns `/api` in production.
- Default network binding is loopback; never make dev server public by default.
- Test on Windows and POSIX when changing subprocess or signal-handling logic.
- Treat all untrusted frontend files and paths cautiously (no traversal or accidental SPA fallbacks on API routes).
- Don't promise 1,000-user scalability without representative load tests; stateful data must be externalized.
- Add tests and update the README for every visible behavior change.

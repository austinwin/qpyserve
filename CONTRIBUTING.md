# Contributing

QPyServe should remain thin and understandable. Preserve standard FastAPI/Vite
behavior; avoid proprietary UI components, hidden auth systems, or mandatory
infrastructure services.

## Setup and checks

1. Use Python 3.10+ in a virtual environment.
2. Run `python -m pip install -e ".[dev]"`.
3. Run `python -m ruff check src tests examples`.
4. Run `python -m pytest -q` and `python -m build`.
5. For Vite changes, test the React counter with `python main.py` and
   `python main.py --build` after installing Node.js.

Add regression tests for all observable changes, especially path handling, Vite
proxying, subprocess management, and API/SPA routing. Keep dependencies minimal.

## Conventions

- Use type hints for public signatures, clear docstrings, and focused modules.
- Keep `run(app, frontend="frontend", port=1111)` backward-compatible.
- Preserve localhost-only development and standard FastAPI authorization semantics.
- Never present test success as a security certification or benchmark result.

Include a minimal reproduction and sanitized logs with bug reports.
Follow [SECURITY.md](SECURITY.md) for security vulnerabilities.

## 0.5.0 feature verification

For Typed API changes, run `python -m pytest tests/test_client.py tests/test_trace.py`
and check the generated TypeScript compiles with the CI TypeScript version.
For Ship changes, run `python -m pytest tests/test_ship.py` and the CI
`ship-docker-smoke` job to verify an actual production image.

Keep generated clients opt-in, preserve plain HTML without Node.js, and do not
bypass FastAPI validation or authentication. Release instructions are in
[RELEASING.md](RELEASING.md).

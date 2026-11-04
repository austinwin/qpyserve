"""Run QPyServe Trace's documented success and failure scenarios.

Run `python main.py` locally, then interact with the browser demo. Trace is
development-only; this example intentionally includes unprotected failure routes.
"""

from fastapi import FastAPI, HTTPException
from qpyserve import run

app = FastAPI(title="QPyServe Trace 0.4 example")


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI"}


@app.get("/api/failure")
def failure() -> None:
    raise HTTPException(status_code=503, detail="Example service unavailable")


@app.get("/api/rate-limit")
def rate_limit() -> None:
    raise HTTPException(status_code=429, detail="Example rate limit")


@app.get("/api/crash")
def crash() -> None:
    # Trace records the exception *type* and project-relative source location.
    # It deliberately omits exception messages and sensitive local paths.
    raise RuntimeError("Intentional demo-only Python failure")


if __name__ == "__main__":
    run(app, frontend="frontend", port=1111)

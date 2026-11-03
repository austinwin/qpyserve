"""Try Trace: python main.py, then click buttons on the page."""

from fastapi import FastAPI, HTTPException
from qpyserve import run

app = FastAPI(title="QPyServe Trace example")


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI"}


@app.get("/api/failure")
def failure() -> None:
    raise HTTPException(status_code=503, detail="Example upstream unavailable")


if __name__ == "__main__":
    run(app, frontend="frontend", port=1111)

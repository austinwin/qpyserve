"""Run both your Python API and frontend using `python main.py`."""

from datetime import datetime, timezone

from fastapi import FastAPI
from qpyserve import run

app = FastAPI(title="QPyServe Starter")


@app.get("/api/hello")
def hello() -> dict[str, str]:
    """A real FastAPI endpoint, accessible to browser and external clients."""
    return {
        "message": "Hello from Python!",
        "time": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    run(app, frontend="frontend", port=1111)

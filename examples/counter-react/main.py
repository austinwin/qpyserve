"""Run with python main.py; qpyserve starts Vite automatically."""

from threading import Lock

from fastapi import FastAPI
from qpyserve import run

app = FastAPI(title="qpyserve Counter React")
_count = 0
_lock = Lock()


@app.get("/api/count")
def count():
    with _lock:
        return {"count": _count}


@app.post("/api/count/increment")
def increment():
    global _count
    with _lock:
        _count += 1
        return {"count": _count}


@app.post("/api/count/reset")
def reset():
    global _count
    with _lock:
        _count = 0
        return {"count": _count}


if __name__ == "__main__":
    run(app, frontend="frontend", port=1111)

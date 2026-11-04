# Trace 0.5: interactive full-stack debugging demo

Requires QPyServe **0.5.0 or newer**. From the cloned QPyServe repository:

```bash
python -m pip install -e .
cd examples/trace-demo
python main.py
```

Open **http://localhost:1111**. QPyServe launches FastAPI and serves the plain
HTML frontend from the same origin, without installing Node.js.

## Try the scenarios

| Button | What to expect in Trace |
| --- | --- |
| **200 Successful fetch** | FastAPI `GET /api/hello` is captured with status and duration |
| **503 Failed fetch** | The browser failure is joined to `GET /api/failure` by trace ID; HTTP 503 is labeled `server_error` |
| **429 Rate limited** | The failure is categorized `rate_limited` |
| **500 Python exception** | `python_exception` and a project-relative `main.py` source location; the exception message is omitted |
| **503 XMLHttpRequest** | A non-`fetch` request is correlated with the backend, as for XHR-based clients |
| **JavaScript error** | The browser reports an exception type and script location, without recording its message |

Select **Trace** (lower-right) or **Alt+Shift+T**, then **Refresh** and
**Copy AI report**. In the JSON, match `browser_events[*].trace_id` to
`backend_failures[*].id`, or inspect a browser event's attached `backend` object.
The report includes a `qpyserve-trace-v2` format identifier. In 0.5.0,
backend records also include an OpenAPI `operation_id` and, when possible,
a safe `endpoint_source` that points to the Python handler. These details
can appear in the browser event's correlated `backend` object.

The 503 button sends a harmless demonstration query value
`example-only-value`. Verify that this value **does not appear** in the copied
report. Browser paths should be reduced to `/api/[redacted]`; the backend should
show route templates, e.g. `/api/failure`.

## Test process recovery

For Vite-based projects (the [React example](../counter-react/) is one):
run `python main.py`, edit a Python API response, and verify the next
request uses the new code without restarting Vite manually. QPyServe's
cross-platform CI integration checks proxying, Python reload, and clean
shutdown. In this **plain HTML** demo, reload happens via Uvicorn; Node.js
is not required.

Trace is **local development only**. Stop with Ctrl+C. The same application
in `python main.py --prod` does not expose the Trace panel. Never treat the
failure endpoints here as production examples of exception handling.

For privacy and limitations, see [Trace documentation](../../docs/TRACE.md).

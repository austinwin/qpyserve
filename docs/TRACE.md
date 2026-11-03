# QPyServe Trace

QPyServe Trace is a small, local development panel for FastAPI and plain HTML, React, Vue, or other Vite frontends. It is automatically enabled when you run `python main.py` with QPyServe 0.3.0 or newer.

## Get started

Run your application normally, open its page, then click **Trace** in the lower-right corner (or press **Alt+Shift+T**). Trigger an API request or error and select **Refresh**. Select **Copy AI report** to place structured diagnostic JSON on your clipboard.

The panel combines recent Python API requests (route templates, HTTP method/status, elapsed milliseconds, correlation IDs, and exception type) with browser `fetch` failures and basic JavaScript exceptions. A project-relative file/line is included when the Python traceback points inside the project.

Try the interactive [Trace demo](../examples/trace-demo/) to trigger HTTP 503 and JavaScript errors.

## Configuration

Trace starts automatically in development only; it does not run in production or appear in static production bundles. Disable the feature in development if desired:

```python
run(app, frontend="frontend", port=1111, trace=False)
```

The browser client is served at `/__qpyserve/trace.js` and backend snapshots at `/__qpyserve/trace`. Both remain on the local development origin.

## Privacy and limitations

- No request or response bodies, query strings, cookies, authorization headers, client IP addresses, or absolute filesystem paths are stored. Backend routes are recorded as FastAPI path templates rather than expanded parameter values.
- Browser requests have query strings and fragments discarded, and opaque path segments longer than 24 characters masked. Shorter paths and source filenames might still be sensitive. **Review the report before sharing.**
- Browser errors remain in the current tab until you explicitly copy the report. No cloud collection, user account, or telemetry dependency is involved.
- Traces live in a bounded 100-entry in-memory buffer, unique to each local Python process. There is no persistent database.
- This is not full distributed tracing. It does not automatically measure SQL, HTTPX, Redis, or external service timings. Instrument those separately with OpenTelemetry when needed.
- Client `fetch` errors are observed by wrapping browser `fetch`. Axios/XHR or a later replacement of `fetch` may not be observed client-side; API requests still show in the Python timeline.
- Restrictive Content Security Policy configurations may need to permit the same-origin trace script and local panel styles.
- Development servers must not be exposed to the public network, and trace is not an authentication, authorization, or security-auditing feature.

# QPyServe Typed API — FastAPI to a browser client

QPyServe uses FastAPI's existing OpenAPI schema to generate a small TypeScript
client. It keeps your FastAPI routes and Pydantic models as the source of truth.
There is no separate schema language, hosted generator or runtime dependency.

## One-command development (opt-in)

In a normal Vite + FastAPI project:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from qpyserve import run

app = FastAPI()

class Sensor(BaseModel):
    pressure: float
    name: str

@app.get("/api/sensors/{sensor_id}", response_model=Sensor, operation_id="getSensor")
def get_sensor(sensor_id: int):
    return Sensor(pressure=42.5, name=f"Sensor {sensor_id}")

if __name__ == "__main__":
    run(app, frontend="frontend", client="frontend/src/qpyserve-api.ts")
```

Run `python main.py`. QPyServe writes `frontend/src/qpyserve-api.ts` **before**
Vite starts, and regenerates it when Python edits restart FastAPI. Only files
containing the QPyServe generator marker can be updated; hand-written files
are protected. No generated file is served by QPyServe's private runtime.

In your React/Vue/TypeScript code (Vite transpiles TypeScript):

```ts
import { api, QPyServeApiError } from "./qpyserve-api";

const sensor = await api.getSensor({ path: { sensor_id: 12 } });
// sensor.pressure is typed as number

try {
  await api.getSensor({ path: { sensor_id: 12 } });
} catch (error) {
  if (error instanceof QPyServeApiError) {
    console.log(error.status, error.operation, error.traceId);
  }
}
```

Types cover JSON request bodies, path/query/header parameters, successful JSON
responses, and Pydantic model references. Optional inputs are optional in TS.
For multi-valued query inputs, URLSearchParams sends repeated query keys.
API calls use same-origin fetch; existing browser sessions/cookies follow the
browser's normal credentials policy.

## CLI for existing projects and AI agents

```bash
qpyserve api
qpyserve api --app main:app --out frontend/src/qpyserve-api.ts
qpyserve api --check --json
```

The CLI imports your project's FastAPI module to obtain OpenAPI; **unlike
`qpyserve doctor`, this executes trusted application imports**. The `--check`
flag does not write anything and exits with status 1 when the generated file
does not match the schema. JSON output reports generated and skipped operations.
Commit the generated file if your deployment builds the frontend before
starting Python, and use `--check` in CI to catch stale contracts.

## Trace correlation

The generated API client uses native `fetch`, so QPyServe's existing
development-only Trace intercepts it automatically. A failed request carries
an optional trace ID. Trace records its OpenAPI operation ID, HTTP status,
route template, timing, and **project-relative Python handler location**.
The copied AI report links browser failures to these backend details without
collecting request bodies, secrets, raw URLs or query strings.

Trace is disabled in production. `QPyServeApiError.traceId` is null when no
trace header is present. This is correlation, **not** a root-cause analyzer.

## Scope and limitations

- JSON request and successful JSON response operations are supported; multipart
  uploads, streaming/binary or text responses, cookie parameters, and external
  OpenAPI references are not generated and appear in `skipped` output.
- JavaScript-only static HTML projects can continue using `fetch` directly;
  auto TypeScript generation is intended for Vite (React/Vue/TS) projects.
- Regeneration is opt-in via `client=` in `run(...)`. Production startup
  does not regenerate or serve TypeScript source.
- Types are compile-time contracts, not runtime validation. FastAPI still
  validates requests, and authentication remains application-specific.
- The generated client intentionally stays small. For broad OpenAPI features,
  multi-service SDKs, or specialized OAuth flows, use an established OpenAPI
  generator instead.

Use `python main.py --build` to produce Vite assets (and update an opted-in
typed client) before production deployment.

# QPyServe Data Bridge demo

A no-Node HTML frontend querying a **lazy one-million-row DuckDB relation**.

```bash
python -m pip install -e ".[data]"  # From the QPyServe repository root
cd examples/data-bridge
python main.py
```

Open <http://localhost:1111>. Adjust pressure/status filters, sort direction,
and pagination. Only 50 selected rows travel to the browser per request.
No million-row Python list is created and no SQL is constructed from raw input
in the browser.

The server registers the dataset once using `DataBridge(app, public=True)`.
`public=True` is only for a synthetic demo! Private data requires
`dependencies=[Depends(require_user)]` plus tenant-specific source scoping.

## Arrow in a React/Vue frontend

The bundled browser module sends an Arrow IPC stream on request. Install
the established JavaScript reader in your frontend:

```bash
npm install apache-arrow
```

```js
import { tableFromIPC } from "apache-arrow";
import { dataset } from "/api/data/_client.js";

const readings = dataset("readings");
const bytes = await readings.arrow({
  columns: ["id", "pressure_psi"],
  filters: [{ column: "pressure_psi", op: "gte", value: 65 }],
  limit: 2000
});
const table = tableFromIPC(bytes); // Columnar data, not an array of JS objects
```

For real data, replace the synthetic relation with:

```python
bridge.parquet("pipes", "data/pipes.parquet")
```

See [Data Bridge docs](../../docs/DATA_BRIDGE.md) for access controls,
bounded query semantics, Arrow/JSON differences and limitations.

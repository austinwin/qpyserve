# Zero-configuration CSV dashboard synchronization

This demonstrates the **simplest full-stack Data Bridge workflow**: one
Python data source registration plus one JavaScript subscription.

From the QPyServe repository root:

```bash
python -m pip install -e ".[data]"
cd examples/data-watch
python main.py
```

Open <http://localhost:1111>. Then edit
`examples/data-watch/data/pumpage.csv`, change a number and save. The
dashboard will refresh automatically on the next 3-second version check
without restarting Python or refreshing your browser.

The example values are **synthetic demonstration data**, not actual water
production measurements.

```python
DataBridge(app, public=True, sources={"pumpage": "data/pumpage.csv"})
```

```js
import { data } from "/api/data/_client.js";
const stop = data("pumpage").watch(({rows}) => updateDashboard(rows));
```

For real applications, use `dependencies=[Depends(require_user)]` instead
of `public=True` and scope any tenant data appropriately. The default
limit is 1,000 records per query; watcher checks are cheap file-stat requests,
and data rows are re-queried **only when the source changes**.

Use Parquet instead of CSV for bigger analytical data. For now, this
simplified workflow supports file sources, not remote API ingestion,
automatic analytics, or visual dashboard generation.

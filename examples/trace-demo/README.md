# QPyServe Trace demo

After installing QPyServe from this repository (or PyPI 0.3.0+):

```bash
cd examples/trace-demo
python main.py
```

Open http://localhost:1111 and click the **Successful API request**, **HTTP 503 failure**, or **Throw JavaScript error** buttons. Select **Trace** in the bottom-right corner (or press Alt+Shift+T). **Copy AI report** copies diagnostic JSON after refreshing the backend request list.

Trace is development-only. `python main.py --prod` serves the same app without the Trace panel.

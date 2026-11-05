"""Cross-platform integration: real Vite proxy, Python reload, and clean exit."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from qpyserve._cli import create_project


def two_ports() -> int:
    for _ in range(100):
        with socket.socket() as first:
            first.bind(("127.0.0.1", 0))
            port = first.getsockname()[1]
        if port >= 65534:
            continue
        try:
            with socket.socket() as second:
                second.bind(("127.0.0.1", port + 1))
            return port
        except OSError:
            pass
    raise RuntimeError("No free loopback port pair")


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def until(check, process: subprocess.Popen, timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Launcher exited early: " + str(process.returncode))
        try:
            if check():
                return
        except Exception:
            pass
        time.sleep(0.4)
    raise AssertionError("Timed out waiting for expected runtime behavior")


def shutdown(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        process.send_signal(
            signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT
        )
        process.wait(timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)


def port_closed(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return False
    except OSError:
        return True


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="qpyserve-smoke-",
                                         ignore_cleanup_errors=os.name == "nt") as temp:
        root = Path(temp)
        project = create_project(root / "app", template="react")
        port = two_ports()
        entry = project / "main.py"
        source = entry.read_text(encoding="utf-8")
        assert "port=1111" in source
        entry.write_text(source.replace("port=1111", f"port={port}"), encoding="utf-8")
        logfile = root / "runtime.log"
        flags = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                 if os.name == "nt" else {"start_new_session": True})
        with logfile.open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "main.py"], cwd=project,
                                       stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, **flags)
            try:
                base = f"http://127.0.0.1:{port}"
                until(lambda: fetch_json(base + "/api/hello").get("message")
                      == "Hello from Python!", process)
                until(lambda: b"html" in urlopen(base + "/", timeout=3).read().lower(),
                      process)
                snapshot = fetch_json(base + "/__qpyserve/trace")
                assert snapshot["version"] == 2
                assert any(x["route"] == "/api/hello" for x in snapshot["requests"])
                entry.write_text(
                    source.replace("port=1111", f"port={port}")
                    .replace("Hello from Python!", "RELOADED"),
                    encoding="utf-8",
                )
                until(lambda: fetch_json(base + "/api/hello").get("message") == "RELOADED",
                      process, timeout=90)
                assert process.poll() is None
            except Exception:
                log.flush()
                print(logfile.read_text(encoding="utf-8", errors="replace")[-10000:])
                raise
            finally:
                shutdown(process)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not (port_closed(port) and port_closed(port + 1)):
            time.sleep(0.3)
        assert port_closed(port), "Vite leaked frontend port after shutdown"
        assert port_closed(port + 1), "Uvicorn leaked backend port after shutdown"
        # Both processes must write through the launcher's inherited output
        # stream, including on Windows when no extra console is created.
        output = logfile.read_text(encoding="utf-8", errors="replace")
        for marker in ("VITE", "Uvicorn running", "[qpyserve] http://localhost:", "GET /api/hello"):
            assert marker in output, f"Missing {marker!r} in combined logs:\n{output[-6000:]}"
        print("Proxy, Trace, combined logs, Python reload, clean shutdown: PASS")


if __name__ == "__main__":
    main()

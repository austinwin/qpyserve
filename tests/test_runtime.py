import os
import sys

from fastapi import FastAPI
import pytest

from qpyserve import run


def test_run_validates_app(tmp_path):
    with pytest.raises(TypeError):
        run(object(), frontend=tmp_path)


def test_run_rejects_bad_port(tmp_path):
    with pytest.raises(ValueError, match="port"):
        run(FastAPI(), frontend=tmp_path, port=0)


def test_run_rejects_multiple_dev_workers(tmp_path):
    with pytest.raises(ValueError, match="workers"):
        run(FastAPI(), frontend=tmp_path, workers=2, mode="development")


def test_run_rejects_missing_frontend(tmp_path):
    with pytest.raises(FileNotFoundError, match="Frontend directory"):
        run(FastAPI(), frontend=tmp_path / "missing", mode="production")


def test_build_only_does_not_start_server(tmp_path, monkeypatch):
    import qpyserve._runtime as rt

    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"devDependencies":{"vite":"^6"}}')
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "main.py"), "--build"])
    calls = []
    monkeypatch.setattr(rt, "build_frontend", lambda _: calls.append("build"))
    monkeypatch.setattr(rt.uvicorn, "run", lambda *_a, **_kw: calls.append("serve"))
    run(FastAPI(), frontend=frontend)
    assert calls == ["build"]


def test_production_missing_build_explains_one_command_option(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"devDependencies":{"vite":"^6"}}')
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "main.py")])
    with pytest.raises(FileNotFoundError, match="--prod --build"):
        run(FastAPI(), frontend=frontend, mode="production")

def test_development_does_not_expose_vite_on_network(tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        run(FastAPI(), frontend=tmp_path, host="0.0.0.0")


def test_vite_build_dir_cannot_escape_frontend(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"devDependencies":{"vite":"^6"}}')
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "main.py")])
    with pytest.raises(ValueError, match="dist must"):
        run(FastAPI(), frontend=frontend, dist="../private")



def test_supervision_stops_both_processes_if_backend_crashes(monkeypatch, tmp_path):
    from qpyserve import _runtime

    class Process:
        def __init__(self, status):
            self.status = status
        def poll(self):
            return self.status

    vite, backend = Process(None), Process(1)
    commands = []
    stopped = []
    processes = iter([vite, backend])
    monkeypatch.setattr(_runtime.subprocess, "Popen",
                        lambda command, **kw: (commands.append((command, kw))
                                               or next(processes)))
    monkeypatch.setattr(_runtime, "_stop_process", stopped.append)
    with pytest.raises(RuntimeError, match="FastAPI exited with status 1"):
        _runtime._supervise_dev(["npm", "exec", "vite"], tmp_path, tmp_path, 1111)
    assert len(commands) == 2
    assert commands[1][0][0] == sys.executable
    assert ("--reload" in commands[1][0]) == (os.name != "nt")
    assert commands[1][1]["cwd"] == tmp_path
    assert stopped == [backend, vite]


def test_supervision_detects_frontend_crash(monkeypatch, tmp_path):
    from qpyserve import _runtime

    class Process:
        def __init__(self, status):
            self.status = status
        def poll(self):
            return self.status

    vite, backend = Process(2), Process(None)
    stopped = []
    processes = iter([vite, backend])
    monkeypatch.setattr(_runtime.subprocess, "Popen",
                        lambda *_a, **_kw: next(processes))
    monkeypatch.setattr(_runtime, "_stop_process", stopped.append)
    with pytest.raises(RuntimeError, match="Vite exited with status 2"):
        _runtime._supervise_dev(["npm"], tmp_path, tmp_path, 1111)
    assert stopped == [backend, vite]


def test_supervision_ctrl_c_cleans_up_children(monkeypatch, tmp_path):
    import signal
    from qpyserve import _runtime

    old_termination_handler = signal.getsignal(signal.SIGTERM)

    class Process:
        def poll(self):
            return None

    vite, backend = Process(), Process()
    processes = iter([vite, backend])
    stopped = []
    monkeypatch.setattr(_runtime.subprocess, "Popen",
                        lambda *_a, **_kw: next(processes))
    monkeypatch.setattr(_runtime, "_stop_process", stopped.append)
    monkeypatch.setattr(_runtime.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt))
    _runtime._supervise_dev(["npm"], tmp_path, tmp_path, 1111)
    assert stopped == [backend, vite]
    assert signal.getsignal(signal.SIGTERM) == old_termination_handler


def test_dev_backend_uses_project_reload_scope(tmp_path):
    from qpyserve._runtime import _dev_process_command

    command = _dev_process_command(tmp_path, 2222)
    assert "--reload" in command
    assert command[command.index("--reload-dir") + 1] == str(tmp_path)
    assert command[command.index("--port") + 1] == "2222"
    assert "node_modules/*" in command



def test_windows_reload_command_does_not_launch_uvicorn_reloader(tmp_path):
    from qpyserve._runtime import _dev_process_command

    command = _dev_process_command(tmp_path, 1112, reload=False)
    assert "--reload" not in command
    assert command[command.index("--port") + 1] == "1112"


def test_python_snapshot_tracks_changes_but_ignores_js_dependencies(tmp_path):
    from qpyserve._runtime import _python_snapshot

    (tmp_path / "main.py").write_text("a = 1")
    original = _python_snapshot(tmp_path)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.py").write_text("data = 1")
    assert _python_snapshot(tmp_path) == original
    (tmp_path / "main.py").write_text("a = 123")
    assert _python_snapshot(tmp_path) != original
    (tmp_path / "main.py").unlink()
    assert _python_snapshot(tmp_path) == ()


def test_supervisor_restarts_backend_only_on_python_edit(tmp_path, monkeypatch):
    from qpyserve import _runtime

    class Process:
        def poll(self):
            return None

    vite, first, reloaded = Process(), Process(), Process()
    processes = iter([vite, first, reloaded])
    stopped = []
    snapshots = iter([("before",), ("after",)])
    tick = iter(range(100))
    monkeypatch.setattr(_runtime.subprocess, "Popen",
                        lambda *_a, **_kw: next(processes))
    monkeypatch.setattr(_runtime, "_stop_process", stopped.append)
    monkeypatch.setattr(_runtime, "_python_snapshot", lambda *_a: next(snapshots))
    monkeypatch.setattr(_runtime.time, "monotonic", lambda: next(tick))
    monkeypatch.setattr(_runtime.time, "sleep",
                        lambda _: (_ for _ in ()).throw(KeyboardInterrupt))
    _runtime._supervise_dev(["npm"], tmp_path, tmp_path, 1111, reload_on_change=True)
    assert stopped == [first, reloaded, vite]

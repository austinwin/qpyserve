"""No network/npm installation required: subprocess calls are stubbed."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from qpyserve._tooling import (
    build_frontend, ensure_dependencies, has_vite, normalize_api_paths,
    package_manager, vite_command, vite_config,
)


def make_vite(tmp_path: Path, *, scripts=None, manager=None):
    package = {"devDependencies": {"vite": "^6"}, "scripts": scripts or {}}
    if manager:
        package["packageManager"] = manager
    (tmp_path / "package.json").write_text(json.dumps(package))
    return tmp_path


def test_detect_vite_without_dev_script(tmp_path):
    make_vite(tmp_path)
    assert has_vite(tmp_path)
    assert package_manager(tmp_path) == "npm"


@pytest.mark.parametrize("lock,expected", [
    ("package-lock.json", "npm"), ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"), ("bun.lock", "bun"),
])
def test_choose_lockfile_package_manager(tmp_path, lock, expected):
    make_vite(tmp_path)
    (tmp_path / lock).write_text("{}")
    assert package_manager(tmp_path) == expected


def test_package_manager_field_precedes_lockfile(tmp_path):
    make_vite(tmp_path, manager="pnpm@9.0.0")
    (tmp_path / "package-lock.json").write_text("{}")
    assert package_manager(tmp_path) == "pnpm"


@pytest.mark.parametrize("invalid", ["/", "api", "//ws", "/a/../b", "/api?x", "/a/*"])
def test_invalid_api_prefixes(invalid):
    with pytest.raises(ValueError):
        normalize_api_paths([invalid])


def test_api_paths_deduplicated_and_custom_websocket_proxy(tmp_path):
    make_vite(tmp_path)
    paths = normalize_api_paths(["/api", "/ws/", "/reports"])
    assert paths.count("/api") == 1
    config = vite_config(tmp_path, host="127.0.0.1", port=1111,
                         backend_port=1112, api_paths=paths).read_text()
    assert "^/ws(?:/|$)" in config
    assert "^/reports(?:/|$)" in config
    assert '"ws": true' in config
    assert "1112" in config


def test_package_install_is_automatic_and_uses_lockfile(tmp_path, monkeypatch):
    make_vite(tmp_path)
    (tmp_path / "package-lock.json").write_text("{}")
    monkeypatch.setattr("qpyserve._tooling.shutil.which", lambda _: "/usr/bin/npm")
    call = Mock()
    monkeypatch.setattr("qpyserve._tooling.subprocess.run", call)
    assert ensure_dependencies(tmp_path, "npm") == ["/usr/bin/npm"]
    call.assert_called_once_with(["/usr/bin/npm", "ci"], cwd=tmp_path, check=True)


def test_vite_does_not_require_dev_script():
    assert vite_command(["npm"], "npm", "--config", "generated.mjs") == [
        "npm", "exec", "--no", "--", "vite", "--config", "generated.mjs"
    ]


def test_build_falls_back_to_vite_without_build_script(tmp_path, monkeypatch):
    make_vite(tmp_path)
    monkeypatch.setattr("qpyserve._tooling.ensure_dependencies", lambda *_: ["npm"])
    call = Mock()
    monkeypatch.setattr("qpyserve._tooling.subprocess.run", call)
    build_frontend(tmp_path)
    call.assert_called_once_with(
        ["npm", "exec", "--no", "--", "vite", "build"],
        cwd=tmp_path, check=True,
    )


def test_build_uses_custom_build_script(tmp_path, monkeypatch):
    make_vite(tmp_path, scripts={"build": "my-custom-build"})
    monkeypatch.setattr("qpyserve._tooling.ensure_dependencies", lambda *_: ["npm"])
    call = Mock()
    monkeypatch.setattr("qpyserve._tooling.subprocess.run", call)
    build_frontend(tmp_path)
    call.assert_called_once_with(["npm", "run", "build"], cwd=tmp_path, check=True)


def test_yarn_pnp_does_not_require_node_modules(tmp_path, monkeypatch):
    make_vite(tmp_path)
    (tmp_path / ".pnp.cjs").touch()
    monkeypatch.setattr("qpyserve._tooling.shutil.which", lambda _: "/usr/bin/yarn")
    call = Mock()
    monkeypatch.setattr("qpyserve._tooling.subprocess.run", call)
    assert ensure_dependencies(tmp_path, "yarn") == ["/usr/bin/yarn"]
    call.assert_not_called()

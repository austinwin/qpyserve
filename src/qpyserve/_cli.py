"""Small, dependency-free command-line tools for QPyServe applications."""

from __future__ import annotations

import argparse
from importlib.resources import files
import json
from pathlib import Path
import shutil
from typing import Any, Sequence

from . import __version__
from ._ship import prepare_ship
from ._tooling import _manager_command, has_vite, package_manager


_STARTER_NAMES = ("html", "react", "vue")


def _copy_template(source: Any, destination: Path) -> None:
    """Copy files from a packaged template, including zipped distributions."""
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            target.mkdir()
            _copy_template(child, target)
        else:
            target.write_bytes(child.read_bytes())


def create_project(path: str | Path, template: str = "html") -> Path:
    """Create a self-contained starter without overwriting existing files."""
    if template not in _STARTER_NAMES:
        raise ValueError(f"Unknown starter: {template!r}")
    target = Path(path).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Destination already exists: {target}")
    if not target.parent.is_dir():
        raise FileNotFoundError(f"Parent directory does not exist: {target.parent}")

    root = files("qpyserve").joinpath("_starters")
    target.mkdir()
    try:
        _copy_template(root.joinpath("common"), target)
        _copy_template(root.joinpath(template), target)
    except Exception:
        # Only remove the directory that was just created. Never delete user data.
        shutil.rmtree(target)
        raise
    return target


def inspect_project(path: str | Path) -> dict[str, object]:
    """Check starter requirements; does not run code or inspect private data."""
    project = Path(path).expanduser().absolute()
    checks: list[dict[str, str]] = []

    def check(status: str, name: str, detail: str) -> None:
        checks.append({"status": status, "name": name, "detail": detail})

    frontend_type = "unknown"
    if not project.is_dir():
        check("error", "project", "Directory does not exist")
    else:
        if (project / "main.py").is_file():
            check("ok", "main.py", "Python entry point found")
        else:
            check("warning", "main.py", "No main.py; use your own Python entry point")

        frontend = project / "frontend"
        if not frontend.is_dir():
            check("error", "frontend", "Missing frontend/ directory")
        else:
            try:
                vite = has_vite(frontend)
            except (ValueError, TypeError, AttributeError) as exc:
                vite = False
                check("error", "package.json", str(exc))
            if vite:
                frontend_type = "vite"
                if (frontend / "index.html").is_file():
                    check("ok", "frontend", "Vite project detected")
                else:
                    check("error", "frontend", "Vite project needs frontend/index.html")
                try:
                    manager = package_manager(frontend)
                    command = _manager_command(manager)
                    check("ok", "package manager", f"{manager}: {command[0]}")
                except (ValueError, RuntimeError) as exc:
                    check("error", "package manager", str(exc))
                if not shutil.which("node") and not shutil.which("bun"):
                    check("error", "JS runtime", "Install Node.js or Bun for Vite development")
                if not (frontend / "node_modules" / "vite").exists() and not (
                    frontend / ".pnp.cjs"
                ).exists():
                    check("info", "dependencies", "Missing packages install automatically on first run")
            else:
                frontend_type = "html"
                if (frontend / "index.html").is_file():
                    check("ok", "frontend", "Plain HTML works without Node.js")
                else:
                    check("error", "frontend", "Missing frontend/index.html")
            if (frontend / ".env").exists():
                check("warning", "secrets", "Keep .env files outside frontend/ (even if blocked)")

    return {
        "project": str(project),
        "frontend": frontend_type,
        "ready": not any(c["status"] == "error" for c in checks),
        "checks": checks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qpyserve",
        description="One-command FastAPI + HTML, React, or Vue.",
    )
    parser.add_argument("--version", action="version", version=f"qpyserve {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="Create a working full-stack project")
    new.add_argument("directory", help="New directory for the application")
    new.add_argument("--template", choices=_STARTER_NAMES, default="html")
    doctor = commands.add_parser("doctor", help="Check a project's development setup")
    doctor.add_argument("directory", nargs="?", default=".")
    doctor.add_argument("--json", action="store_true", help="Machine-readable diagnostics for AI tools")
    ship = commands.add_parser("ship", help="Generate Docker and Render deployment files")
    ship.add_argument("directory", nargs="?", default=".")
    ship.add_argument("--app", default="main:app", help="Import path, for example main:app")
    ship.add_argument("--name", help="Render service name")
    ship.add_argument("--json", action="store_true", help="Machine-readable result for AI tools")
    args = parser.parse_args(argv)

    if args.command == "new":
        try:
            target = create_project(args.directory, template=args.template)
        except (OSError, ValueError) as exc:
            parser.exit(1, f"qpyserve: {exc}\n")
        print(f"Created {args.template} + FastAPI project in {target}")
        print(f"\n  cd \"{target}\"\n  python main.py\n")
        if args.template != "html":
            print("Node.js or Bun is required for Vite; dependencies install on first run.")
        return 0

    if args.command == "ship":
        try:
            result = prepare_ship(args.directory, app_import=args.app, service_name=args.name)
        except (OSError, ValueError, TypeError) as exc:
            parser.exit(1, f"qpyserve: {exc}\n")
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Deployment files created in {result['project']}:")
            for name in result["files"]:
                print(f"  {name}")
            print("Review generated files, commit and push to GitHub, then create a Render Blueprint.")
            print("No application was deployed. Render free instances sleep and have ephemeral storage.")
            print("Protect public routes and configure secrets on your hosting provider.")
        return 0

    result = inspect_project(args.directory)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"QPyServe doctor: {result['project']} ({result['frontend']})")
        for item in result["checks"]:
            print(f"  {item['status'].upper():7} {item['name']}: {item['detail']}")
        print("Checks startup requirements only; not a security or load-test certification.")
    return 0 if result["ready"] else 1

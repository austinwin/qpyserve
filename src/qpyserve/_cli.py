"""Small, dependency-free command-line tools for QPyServe applications."""

from __future__ import annotations

import argparse
from importlib.resources import files
import json
from pathlib import Path
import shutil
from typing import Any, Sequence

from . import __version__
from ._client import client_output, generate_client, load_app, save_client
from ._ship import prepare_ship
from ._tooling import _manager_command, has_vite, package_manager


_STARTER_NAMES = ("html", "react", "vue", "dashboard")


def _copy_template(source: Any, destination: Path) -> None:
    """Copy files from a packaged template, including zipped distributions."""
    for child in source.iterdir():
        # Wheels may include bytecode caches from their build environment.
        # These are not starter source files and must never be copied.
        if child.name == "__pycache__" or child.name.endswith((".pyc", ".pyo")):
            continue
        target = destination / child.name
        if child.is_dir():
            if target.is_symlink():
                raise ValueError(f"Refusing to copy through a symlink: {target}")
            # common/ and the selected template intentionally overlay folders.
            target.mkdir(exist_ok=True)
            _copy_template(child, target)
        else:
            target.write_bytes(child.read_bytes())


def create_project(
    path: str | Path,
    template: str = "html",
    *,
    data_source: str | Path | None = None,
    public_data: bool = False,
) -> Path:
    """Create a starter without overwriting existing files or publishing data silently."""
    if template not in _STARTER_NAMES:
        raise ValueError(f"Unknown starter: {template!r}")
    source = None
    if data_source is not None or public_data:
        if template != "dashboard" or data_source is None:
            raise ValueError("--data and --public-data apply only to the dashboard template")
        if not public_data:
            raise ValueError("Custom dashboard data requires explicit --public-data acknowledgement")
        source = Path(data_source).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() != ".csv":
            raise ValueError("--data must point to an existing CSV file")
        # Protect against accidentally copying very large files into public demos.
        if source.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("--data CSV exceeds the 20 MB starter import limit")
        import csv

        with source.open("r", encoding="utf-8-sig", newline="") as file:
            header = next(csv.reader(file), [])
        if len(header) < 2 or not all(header):
            raise ValueError("--data CSV needs at least two named columns")
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
        if source is not None:
            shutil.copyfile(source, target / "data" / "sample.csv")
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
    new.add_argument("--data", help="Existing CSV for dashboard starter (requires --public-data)")
    new.add_argument("--public-data", action="store_true", help="Acknowledge public CSV exposure")
    doctor = commands.add_parser("doctor", help="Check a project's development setup")
    doctor.add_argument("directory", nargs="?", default=".")
    doctor.add_argument("--json", action="store_true", help="Machine-readable diagnostics for AI tools")
    ship = commands.add_parser("ship", help="Generate Docker and Render deployment files")
    ship.add_argument("directory", nargs="?", default=".")
    ship.add_argument("--app", default="main:app", help="Import path, for example main:app")
    ship.add_argument("--name", help="Render service name")
    ship.add_argument("--json", action="store_true", help="Machine-readable result for AI tools")
    api = commands.add_parser("api", help="Generate a typed TypeScript client from FastAPI")
    api.add_argument("directory", nargs="?", default=".")
    api.add_argument("--app", default="main:app", help="Local FastAPI import path")
    api.add_argument("--out", help="Output .ts path within frontend/ (never overwrite hand-written files)")
    api.add_argument("--check", action="store_true", help="Fail if generated client has drifted")
    api.add_argument("--json", action="store_true", help="Machine-readable result")
    args = parser.parse_args(argv)

    if args.command == "new":
        try:
            target = create_project(
                args.directory, template=args.template,
                data_source=args.data, public_data=args.public_data,
            )
        except (OSError, ValueError) as exc:
            parser.exit(1, f"qpyserve: {exc}\n")
        print(f"Created {args.template} + FastAPI project in {target}")
        print(f"\n  cd \"{target}\"\n  python main.py\n")
        if args.template in ("react", "vue"):
            print("Node.js or Bun is required for Vite; dependencies install on first run.")
        elif args.template == "dashboard":
            print('Requires: python -m pip install "qpyserve[data]>=0.7.1"')
            print("WARNING: Dashboard data is public. Protect it before deploying private data.")
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

    if args.command == "api":
        try:
            project = Path(args.directory).expanduser().resolve()
            app = load_app(project, args.app)
            generated = generate_client(app.openapi())
            target = client_output(project, args.out)
            result = save_client(generated, target, check=args.check)
        except (OSError, ValueError, TypeError, ImportError, AttributeError) as exc:
            parser.exit(1, f"qpyserve: {exc}\n")
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(
                f"QPyServe API: {len(result['operations'])} typed operations; "
                f"{len(result['skipped'])} skipped"
            )
            print(
                ("Out of date: " if args.check and result["drift"] else "Client: ")
                + str(target)
            )
            for warning in result["skipped"]:
                print(f"  SKIPPED {warning}")
        return 1 if args.check and result["drift"] else 0

    result = inspect_project(args.directory)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"QPyServe doctor: {result['project']} ({result['frontend']})")
        for item in result["checks"]:
            print(f"  {item['status'].upper():7} {item['name']}: {item['detail']}")
        print("Checks startup requirements only; not a security or load-test certification.")
    return 0 if result["ready"] else 1

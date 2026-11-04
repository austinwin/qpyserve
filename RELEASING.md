# Releasing qpyserve to PyPI

The package is published from GitHub Actions using **PyPI Trusted Publishing (OIDC)**.
Do **not** commit a PyPI API token, add one to the repo, or upload from an untrusted machine.

## First-time setup (one-time, project owner)

1. Sign in to https://pypi.org/. Enable 2FA if you have not already.
2. If `qpyserve` is not yet a project on PyPI, open the PyPI account **Publishing** page and add a **pending publisher** for a new project.
   If it already exists **and you own it**, use its **Manage → Publishing** page instead.
3. Enter the **exact** GitHub trusted publisher values:

   | Field | Value |
   | --- | --- |
   | PyPI project name (pending project only) | `qpyserve` |
   | Owner | `austinwin` |
   | Repository | `qpyserve` |
   | Workflow filename | `publish.yml` |
   | Environment | `pypi` |

4. In GitHub repo **Settings → Environments**, configure the `pypi` environment.
   Restrict deployment to the default branch and release tags, and add reviewer approvals if available.
   The workflow references this environment.
5. From https://github.com/austinwin/qpyserve/actions/workflows/publish.yml
   select **Run workflow** on `main` to publish the first release.
6. Confirm the **Upload to PyPI** job succeeds and verify the public project:
   https://pypi.org/project/qpyserve/
7. In a fresh Python virtual environment, verify:
   `python -m pip install qpyserve==<released-version>` and `python -c "import qpyserve; print(qpyserve.__version__)"`.

**Note:** A pending publisher does **not** reserve a PyPI project name. If the project name
is taken or reserved, PyPI will refuse the upload; do not assume the name is available based
only on search results.

## Subsequent releases

1. Bump `[project].version` in `pyproject.toml` and `__version__` in `src/qpyserve/__init__.py`.
2. Update tests and docs, add the new version's changes and a runnable example to `CHANGELOG.md` and `README.md`, and merge to `main`.
3. Create/push a matching tag, e.g. `v0.1.1`, or use **Run workflow** on `main`.
   Tags are checked against the version in `pyproject.toml`.
4. Confirm the build and publication jobs pass and installation from PyPI works.

The release workflow runs Python tests, builds the React/Vite example, builds a wheel and
sdist, validates distribution metadata, and publishes with short-lived OIDC credentials.
It does not use a stored PyPI token.

Never reuse a PyPI version: release versions are immutable.

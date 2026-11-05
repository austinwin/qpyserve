# Releasing QPyServe to PyPI

QPyServe is published through GitHub Actions using **PyPI Trusted Publishing (OIDC)**, not a stored PyPI token. The normal release path is a versioned Git tag matching the Python package version.

## PyPI publisher configuration

The existing `qpyserve` PyPI project must have this trusted publisher configured:

| Field | Value |
| --- | --- |
| PyPI project | `qpyserve` |
| GitHub owner | `austinwin` |
| GitHub repository | `qpyserve` |
| Workflow filename | `publish.yml` |
| GitHub environment | `pypi` |

Use the PyPI project **Manage → Publishing** page to inspect the configuration. Protect the GitHub `pypi` environment with suitable approval/deployment rules. Do not commit API tokens or upload artifacts from an untrusted workstation.

## Release checklist

1. Confirm the previous PyPI release and select a **new** version; published version numbers cannot be reused.
2. Update `[project].version` in `pyproject.toml` and `__version__` in `src/qpyserve/__init__.py`. These must match.
3. Update `README.md`, `CHANGELOG.md`, feature guides, examples, and tests. Avoid leaving `unreleased` references for features included in the new version.
4. Run `python -m ruff check src tests examples`, `python -m pytest -q`, `python -m build`, and `python -m twine check dist/*`. Wait for all Linux/Windows, React/Vite, typed-client, and Docker CI checks to pass.
5. Merge the release PR to `main`; create a Git tag such as `v0.5.0` on the exact release commit. The `publish.yml` workflow checks that the tag matches `pyproject.toml`.
6. Confirm **both** the build and **Upload to PyPI** jobs succeed. A GitHub environment may require manual approval before upload.
7. Verify the release on [PyPI](https://pypi.org/project/qpyserve/) and with a clean installation:

   ```bash
   python -m pip install --no-cache-dir 'qpyserve[data]==<VERSION>'
   python -c "import qpyserve; print(qpyserve.__version__)"
   qpyserve --version
   qpyserve new smoke-app --template react
   cd smoke-app
   qpyserve api --check --json  # Expected drift before first generation
   qpyserve api
   qpyserve api --check --json  # Should now pass
   ```

8. Announce release notes and point users to the version-specific [changelog](CHANGELOG.md). Check the release tag and PyPI artifacts refer to the same code.

## QPyServe 0.5.0 publishing note

Version `v0.5.0` was released from the verified release commit using a
one-time guarded release workflow, which created the annotated tag and published
to PyPI through Trusted Publishing. The temporary main-branch publication
trigger has since been removed. **Subsequent versions are tag-driven**, as
described in the release checklist.

The publication workflow now verifies the installed PyPI wheel with a clean
Python environment after upload, including version and CLI checks. A failed
install verification must be investigated even if the upload job succeeded.

## One-time 0.6.0 release trigger

The guarded `.github/workflows/release-once-v0.6.0.yml` workflow runs only
when the release PR adds that workflow to `main`. It checks that the package
version is exactly `0.6.0` and that the release tag does not exist, creates
the annotated `v0.6.0` tag on the exact merged commit, and dispatches
`publish.yml` against that tag using the repository's GitHub Actions token.
This is needed because tags pushed with `GITHUB_TOKEN` do not themselves
trigger other workflows. The regular PyPI publishing job still uses Trusted
Publishing with the protected `pypi` environment and verifies a fresh PyPI
installation. After publication, remove the one-time workflow in a cleanup PR.
Do not rerun the one-time tag creator once `v0.6.0` has been created.

## Troubleshooting

- **Package version already exists:** do not overwrite or reuse it; bump the version, update the changelog, and rerun a new release.
- **OIDC trusted-publisher failure:** verify the PyPI owner/repository/workflow/environment match exactly and check the GitHub `pypi` environment approval rules.
- **Build succeeded, upload pending:** approve the environment if policy requires it; do not claim publication until the upload job succeeds.
- **Install returns an older version:** install the explicit new version with `--no-cache-dir`, inspect the public PyPI release, and verify you are using the intended index.
- **Tag and version mismatch:** correct the version and create a new release tag; never retarget an already published release without carefully reconciling artifacts.

The release workflow builds a wheel and sdist, runs unit and frontend checks, verifies distribution contents and metadata, and publishes with short-lived OIDC credentials.

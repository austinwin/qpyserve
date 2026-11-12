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

## QPyServe 0.7.1 recovery (2026-11-12)

The v0.7.0 tag was created, but the upload did **not** happen. The 0.7.0
Publish to PyPI build ran tests against the installed wheel and failed four
dashboard starter tests: the wheel contained a `__pycache__` directory that
was copied twice into the generated starter. The tag remains immutable.

Version 0.7.1 fixes starter copying to skip Python caches and merge overlapping
template directories, and adds a regression test. Once the 0.7.1 release CI
succeeds, the new tag and trusted-publishing workflow publish 0.7.1.
Only claim publication after both the upload and the clean PyPI install succeed.

## QPyServe 0.7.0 release scope

Version 0.7.0 includes the Node-free dashboard starter, CSV/Parquet watchers,
and SQL table/view sources. Release verification must include generated
dashboard packaging, a clean `qpyserve[data]==0.7.0` installation, optional
database tests, and an end-to-end CSV query. The release tag must point to
the exact commit whose wheel was uploaded.

## QPyServe 0.6.0 publishing note

Version `v0.6.0` was tagged from release commit
`40bcc08490afb149fe066907be943f0903f43ce1` using a guarded, one-time
GitHub Actions bootstrap. The bootstrap explicitly dispatched `publish.yml`
against the tag because tag pushes made by `GITHUB_TOKEN` do not trigger
workflows. The regular PyPI Trusted Publishing upload and fresh-install
verification both passed. The temporary release bootstrap has been removed.
Subsequent releases should follow the usual tag-driven checklist above.

## Troubleshooting

- **Package version already exists:** do not overwrite or reuse it; bump the version, update the changelog, and rerun a new release.
- **OIDC trusted-publisher failure:** verify the PyPI owner/repository/workflow/environment match exactly and check the GitHub `pypi` environment approval rules.
- **Build succeeded, upload pending:** approve the environment if policy requires it; do not claim publication until the upload job succeeds.
- **Install returns an older version:** install the explicit new version with `--no-cache-dir`, inspect the public PyPI release, and verify you are using the intended index.
- **Tag and version mismatch:** correct the version and create a new release tag; never retarget an already published release without carefully reconciling artifacts.

The release workflow builds a wheel and sdist, runs unit and frontend checks, verifies distribution contents and metadata, and publishes with short-lived OIDC credentials.

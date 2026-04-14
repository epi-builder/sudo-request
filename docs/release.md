# Release Guide

Use this guide when preparing a PyPI release. This repository uses `uv` for
build and publish commands.

## First Release Checklist

Before publishing `0.1.0`, confirm:

- The package name is available on PyPI and TestPyPI.
- The MIT license is still the intended public license.
- Repository and issue URLs still point at the intended public GitHub project.
- `CHANGELOG.md` has the final release date instead of `Unreleased`.
- The installed update flow has been tested on the target macOS machine.

## Version Bump

```bash
uv run python scripts/bump-version.py 0.1.1
uv run python scripts/check-version.py
```

Update `CHANGELOG.md` in the same change.

## Local Release Check

```bash
scripts/release-check.sh
```

With Task:

```bash
task release:check
```

This runs version consistency, unit tests, CLI smoke checks, compileall, and
`uv build --no-sources`. The `--no-sources` build checks the package without
local source overrides.

For install/update, daemon, sudoers, or IPC changes, also run:

```bash
sudo-request update-itself --source /Users/epikem/dev/projects/sudo-request
SUDO_REQUEST_BIN=sudo-request scripts/e2e-root-manual.sh
sudo-request status
/usr/bin/sudo -n /usr/bin/id -u
```

The final sudo command should fail with a password-required message after the
approved window is cleaned up.

## Release Process

The normal release path is:

```bash
task release:check
export TEST_PYPI_TOKEN="pypi-..."
task release:publish-test
task release:verify-test-pypi
export PYPI_TOKEN="pypi-..."
task release:publish
task release:tag
task release:push-tag
```

`release:publish-test` and `release:publish` build fresh artifacts before
uploading. TestPyPI and PyPI use separate accounts/projects/tokens, so a token
created on `pypi.org` will fail against `test.pypi.org`, and vice versa.

Publish to TestPyPI first:

```bash
uv publish --publish-url https://test.pypi.org/legacy/ dist/*
```

With Task:

```bash
export TEST_PYPI_TOKEN="pypi-..."
task release:publish-test
```

Install from TestPyPI in a clean environment and verify:

```bash
uvx --default-index https://test.pypi.org/simple/ --from sudo-request sudo-request --version
```

With Task:

```bash
task release:verify-test-pypi
```

Publish to PyPI:

```bash
uv publish dist/*
```

With Task:

```bash
export PYPI_TOKEN="pypi-..."
task release:publish
```

Create and push a matching git tag after the PyPI release succeeds:

```bash
git tag v0.1.0
git push origin v0.1.0
```

With Task:

```bash
task release:tag
task release:push-tag
```

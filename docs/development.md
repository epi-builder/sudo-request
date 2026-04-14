# Development Guide

Use `uv` for Python commands.

Run normal checks from the repository root:

```bash
uv run python -m unittest discover -s tests
uv run python -m compileall -q src tests
uv run sudo-request --help
scripts/e2e-smoke.sh
```

Before publishing a package release:

```bash
scripts/release-check.sh
```

`scripts/e2e-smoke.sh` is source-checkout based. It runs unit tests, CLI help,
doctor smoke, and compileall.

Use `rg` for searching. Do not commit `.venv/`, `__pycache__/`, `.pytest_cache/`,
or local logs.

## E2E Testing

Source checkout CLI with installed daemon:

```bash
scripts/e2e-root-manual.sh
```

Installed PATH wrapper with installed daemon:

```bash
SUDO_REQUEST_BIN=sudo-request scripts/e2e-root-manual.sh
```

The root/manual e2e sends a Telegram approval request. The user must press
Approve once. It verifies:

- sudo window is closed before the test
- `/usr/bin/sudo /usr/bin/id -u` returns `0` during the approved run
- daemon reports no stale drop-in
- passwordless sudo fails again after cleanup

## Verification Before Commit

For normal source changes:

```bash
scripts/e2e-smoke.sh
```

For install/update, daemon, sudoers, or IPC behavior changes:

```bash
sudo-request update-itself --source <absolute_path_to_sudo-request_checkout>
SUDO_REQUEST_BIN=sudo-request scripts/e2e-root-manual.sh
```

Confirm the final state:

```bash
sudo-request status
/usr/bin/sudo -n /usr/bin/id -u
```

Only ignored artifacts should remain in `git status --short --ignored`.

## Follow-Up Tracking

- Product improvements are in `tasks.todo`.
- Structural refactoring steps are also tracked in `tasks.todo`.
- Security analysis is in `audit-memo.md`.

When completing a listed item, update the relevant todo file in the same change.

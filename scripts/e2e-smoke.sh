#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/4] unit tests"
uv run python -m unittest discover -s tests

echo "[2/4] CLI help"
uv run sudo-request --help >/dev/null

echo "[3/4] doctor smoke"
uv run sudo-request doctor >/tmp/sudo-request-e2e-doctor.out
grep -q '^config:' /tmp/sudo-request-e2e-doctor.out
grep -q '^daemon socket:' /tmp/sudo-request-e2e-doctor.out

echo "[4/4] compile"
uv run python -m compileall -q src tests

echo "e2e-smoke: ok"

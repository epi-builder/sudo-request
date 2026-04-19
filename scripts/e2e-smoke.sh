#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/4] unit tests"
uv run python -m unittest discover -s tests

echo "[2/4] CLI help"
uv run sudo-request --help >/dev/null

echo "[3/4] doctor smoke"
set +e
uv run sudo-request doctor >/tmp/sudo-request-e2e-doctor.out
doctor_code=$?
set -e
if [[ "$doctor_code" -gt 2 ]]; then
  echo "doctor exited with unexpected code $doctor_code" >&2
  cat /tmp/sudo-request-e2e-doctor.out >&2
  exit 1
fi
grep -q '^config:' /tmp/sudo-request-e2e-doctor.out
grep -q '^daemon socket:' /tmp/sudo-request-e2e-doctor.out

echo "[4/4] compile"
uv run python -m compileall -q src tests

echo "e2e-smoke: ok"

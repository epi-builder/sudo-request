#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/6] version consistency"
uv run python scripts/check-version.py

echo "[2/6] unit tests"
uv run python -m unittest discover -s tests

echo "[3/6] CLI version/help"
uv run sudo-request --version >/dev/null
uv run sudo-request --help >/dev/null

echo "[4/6] compile"
uv run python -m compileall -q src tests scripts

echo "[5/6] build distributions"
rm -rf dist
uv build --no-sources

echo "[6/6] built artifacts"
ls -1 dist/sudo_request-*.tar.gz dist/sudo_request-*.whl >/dev/null

echo "release-check: ok"

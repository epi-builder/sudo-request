#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

WINDOW_SECONDS="${WINDOW_SECONDS:-10}"
SUDO_REQUEST_BIN="${SUDO_REQUEST_BIN:-uv run sudo-request}"
RUN_OUT="/tmp/sudo-request-e2e-run.out"
RUN_ERR="/tmp/sudo-request-e2e-run.err"
PRE_ERR="/tmp/sudo-request-e2e-pre.err"
POST_ERR="/tmp/sudo-request-e2e-post.err"
STATUS_OUT="/tmp/sudo-request-e2e-status.out"

run_sudo_request() {
  # shellcheck disable=SC2086
  $SUDO_REQUEST_BIN "$@"
}

cleanup() {
  run_sudo_request cleanup >/tmp/sudo-request-e2e-cleanup.out 2>/tmp/sudo-request-e2e-cleanup.err || true
  /usr/bin/sudo -k >/dev/null 2>&1 || true
}

trap cleanup EXIT

echo "[1/6] installed command"
echo "using: $SUDO_REQUEST_BIN"
run_sudo_request --help >/dev/null

echo "[2/6] daemon status"
run_sudo_request status >"$STATUS_OUT"
grep -q '"ok": true' "$STATUS_OUT"

echo "[3/6] verify sudo window is closed before test"
/usr/bin/sudo -k >/dev/null 2>&1 || true
if /usr/bin/sudo -n /usr/bin/id -u >/tmp/sudo-request-e2e-pre.out 2>"$PRE_ERR"; then
  echo "error: passwordless sudo is already open before test" >&2
  exit 1
fi
grep -q 'password is required' "$PRE_ERR"

echo "[4/6] request Telegram approval"
echo "Approve the Telegram request for: /usr/bin/sudo /usr/bin/id -u"
run_sudo_request run --window-seconds "$WINDOW_SECONDS" -- /usr/bin/sudo /usr/bin/id -u >"$RUN_OUT" 2>"$RUN_ERR"
cat "$RUN_ERR" >&2
grep -qx '0' "$RUN_OUT"

echo "[5/6] verify daemon reports no stale drop-in"
run_sudo_request status >"$STATUS_OUT"
grep -q '"dropin_exists": false' "$STATUS_OUT"

echo "[6/6] verify sudo window is closed after test"
/usr/bin/sudo -k >/dev/null 2>&1 || true
if /usr/bin/sudo -n /usr/bin/id -u >/tmp/sudo-request-e2e-post.out 2>"$POST_ERR"; then
  echo "error: passwordless sudo is still open after test" >&2
  exit 1
fi
grep -q 'password is required' "$POST_ERR"

echo "e2e-root-manual: ok"

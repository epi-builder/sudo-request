# Daemon State Persistence

The daemon persists active request lifecycle state at:

```text
/var/run/sudo-request/active-request.json
```

The file is runtime recovery state, not an audit log or security boundary.
Daemon audit logs remain the durable history.

## Startup Recovery

On startup, the daemon loads the state file, removes any broad sudoers drop-in,
and keeps the restored request only if it reached an opened sudo window.
Pre-window requests are discarded because their Telegram approval wait cannot be
resumed.

If cleanup fails for a restored request, the daemon keeps enough state to retry
through the watchdog and send cleanup critical alerts.

## Stored Data

The persisted lifecycle contains the request id, payload hash, uid/user, command
metadata, resolved executable, approval message ids, phase, approval expiry,
requested window, window expiry, and exit code when known.

Writes are atomic through a temporary file and `os.replace`, and the state file
is removed when the active request is cleared.

## Verification

Covered by unit tests:

- state write/read/clear
- corrupt state cleanup
- lifecycle updates after restore
- startup discard for pre-window requests
- watchdog reschedule when restored cleanup fails

Manual e2e should still verify final state after daemon/update work:

```bash
sudo-request status
/usr/bin/sudo -n /usr/bin/id -u
```

# Daemon State Persistence Plan

## Problem

The daemon currently keeps the active request lifecycle only in memory. That is
enough for the normal run path, but it loses context when launchd restarts the
daemon, the daemon crashes, the Mac sleeps and wakes at an awkward time, or
`update-itself` reloads the daemon while a request is still running.

The most visible current symptom is self-update: the approval message can remain
at `[RUNNING]` because the old daemon receives the `running` lifecycle event,
then `install` reloads launchd before the CLI can send the final `done` event.
The sudoers rule is cleaned up, but Telegram no longer reflects the terminal
state.

The security-sensitive version of the same class of failure is worse: if a broad
sudoers drop-in remains after daemon death or restart, the next daemon instance
should have enough durable context to clean it up and alert the user.

## Goal

Persist enough daemon state to recover the broad sudo window lifecycle after a
daemon restart. The first durable target is security cleanup and user visibility,
not perfect reconstruction of command execution.

The daemon should be able to:

- notice a persisted active request on startup
- compare persisted state with the actual sudoers drop-in
- retry cleanup when a drop-in may still be installed
- update Telegram with a recovered terminal status when possible
- send a critical Telegram alert if cleanup still fails
- clear persisted state only after a terminal cleanup/recovery decision

## Non-Goals

- Do not move command execution into the daemon.
- Do not make broad mode process-bound.
- Do not claim a command exit code unless the CLI delivered it.
- Do not preserve compatibility with old unpublished state file layouts.

## State File

Use a root-owned state file such as:

```text
/var/run/sudo-request/active-request.json
```

The state is runtime state, not a permanent audit record. Daemon audit logs
remain the durable history. If `/var/run` is cleared across reboot, startup
should still inspect the sudoers drop-in and perform generic cleanup/alerting
when needed.

Required file properties:

- owner `root:wheel`
- mode `0600`
- parent directory not writable by non-root users
- atomic write through temporary file plus `os.replace`
- no symlink following for writes
- tolerate missing or corrupt state by logging and falling back to drop-in
  inspection

Initial fields:

```json
{
  "version": 1,
  "request_id": "...",
  "payload_hash": "...",
  "uid": 501,
  "user": "epikem",
  "host": "...",
  "argv": ["..."],
  "cwd": "...",
  "resolved_executable": "...",
  "parent_process": {"pid": 123},
  "phase": "running",
  "approval_messages": [{"chat_id": 123, "message_id": 456}],
  "requested_window_seconds": 30,
  "max_window_seconds": 300,
  "approval_expires_at": 1776063490,
  "window_opened_at": 1776063460,
  "window_expires_at": 1776063490,
  "exit_code": null,
  "dropin_path": "/private/etc/sudoers.d/sudo-request-broad"
}
```

## Recovery Semantics

On daemon startup:

1. Load the state file if present.
2. Check whether the broad sudoers drop-in exists.
3. If no state exists and no drop-in exists, start normally.
4. If no state exists but a drop-in exists, attempt cleanup and send a generic
   critical Telegram alert if cleanup fails.
5. If state exists and the drop-in exists, attempt cleanup immediately.
6. If cleanup succeeds, update Telegram with a recovered terminal status and
   remove the state file.
7. If cleanup fails, keep the state file, mark the phase failed, and send a
   critical Telegram alert.
8. If state exists but no drop-in exists, update Telegram with a recovered
   closed status when approval message metadata is available, then remove the
   state file.

Recovered Telegram statuses should avoid false precision:

- use `[RECOVERED closed]` when the window is confirmed closed but command exit
  is unknown
- use `[DONE exit=N]` only when the CLI delivered the exit code before restart
- use `[CRITICAL cleanup_failed]` when a drop-in may still be installed

## Write Points

Persist state after each lifecycle transition that changes recovery behavior:

- request created
- approval messages sent
- approved
- window open
- running
- done or failed
- cancelled, denied, expired, closed

Terminal states can remove the active state file once cleanup has been verified
or no broad sudoers drop-in exists.

## Security Notes

The state file contains command metadata and Telegram message ids, so it must not
be user-writable. Treat malformed state as untrusted input: validate request id,
uid, username, phase, and drop-in path before using it.

The actual sudoers drop-in remains the source of truth for whether passwordless
sudo may be open. Persisted state explains why the drop-in exists; it does not
prove that the drop-in exists.

## Implementation Sketch

Add a small daemon-owned module, for example
`src/sudo_request/app/daemon/state_store.py`, responsible for:

- serializing `RequestLifecycle`
- atomic root-owned writes
- loading and validating versioned state
- clearing state after terminal recovery

Then wire the daemon server to:

- write state from `DaemonState` phase changes
- store `window_opened_at` and `window_expires_at` when the sudoers rule opens
- perform startup recovery in `run_foreground` before serving IPC
- reuse the existing cleanup critical alert helper for failed recovery cleanup

Keep Telegram formatting in `lib/approval/message.py` and Telegram transport in
`lib/approval/telegram.py`.

## Verification

Unit tests should cover:

- atomic state write/read/clear
- corrupt or wrong-version state handling
- startup with no state and no drop-in
- startup with state and no drop-in
- startup with state and cleanup success
- startup with state and cleanup failure
- startup with drop-in but no state
- Telegram recovered/critical status behavior

Manual/e2e checks should cover:

- normal approved command still reaches `[DONE exit=N]`
- `update-itself` no longer leaves Telegram indefinitely at `[RUNNING]`
- daemon restart during an open window cleans up or alerts
- final state has no active request, no drop-in, and passwordless sudo fails

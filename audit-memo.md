# sudo-request v1 Broad Mode Security Audit Memo

## Scope

This memo reviews the current `sudo-request` v1 broad-mode implementation.

Current model:

```text
user CLI -> root daemon over Unix socket -> Telegram approval
         -> temporary sudoers drop-in: <user> ALL=(ALL) NOPASSWD: ALL
         -> user CLI runs original command
         -> close request/watchdog removes drop-in
```

This is not a `sudo -v` timestamp substitute. Approval opens a short,
user-wide passwordless sudoers window. The window is not process-bound.

## Main Security Boundary

The real security boundary is the Telegram-approved broad sudo window.

Once approved, every process running as the same local user can run
passwordless sudo until cleanup or TTL expiry. The daemon does not grant root to
only the requested command, and it cannot prevent a compromised same-user
process from racing into the open window.

This is acceptable only under the current assumption: a personal macOS
development machine where the user accepts that same-user compromise is already
high-impact.

## Attack Vectors

1. Same-user process races the broad sudo window

A malicious process already running as the local user can poll for the
passwordless sudo window and run arbitrary root commands while the window is
open. This is the largest structural risk in broad mode.

Current mitigations:
- Window duration is bounded by `broad_window_seconds_max`.
- Default duration is short via `broad_window_seconds_default`.
- CLI can request shorter windows with `--window-seconds`.
- Daemon watchdog removes the sudoers drop-in at TTL.
- CLI sends close request after command exit.
- Telegram approval message explicitly warns that any same-user process can use
  passwordless sudo during the window.

Residual risk:
- A same-user attacker can still win the race during the approved window.
- This cannot be fully fixed without leaving broad mode.

2. Overbroad approved command

The approval payload shows the command, but the granted capability is broader
than the command. A user may approve a harmless-looking command while another
process uses the same window for a different root action.

Current mitigations:
- Telegram message shows requested command, resolved executable, cwd, user,
  host, window duration, expiry, and payload hash.
- The tool's documentation describes broad-mode semantics.

Residual risk:
- User approval does not bind sudo usage to the displayed command.
- This remains a UX/security mismatch inherent to broad sudoers mode.

3. Stale sudoers drop-in remains installed

If cleanup fails, `/private/etc/sudoers.d/sudo-request-broad` could leave the
local user with passwordless sudo indefinitely.

Current mitigations:
- Daemon removes stale drop-in on startup.
- CLI close request removes the drop-in after command execution.
- Watchdog removes the drop-in at TTL even if the CLI does not close cleanly.
- Daemon shutdown tries cleanup.
- `sudo-request cleanup` exists.
- CLI cleanup diagnostics distinguish harmless daemon-restart disconnects from
  cases where the broad rule still exists.
- `status` reports `dropin_exists`.
- Cleanup failure paths send best-effort Telegram critical alerts when the
  broad rule may remain installed.
- `doctor` checks owner/mode/kind for the sudoers directory and broad rule
  drop-in.
- Active request state is persisted under the daemon runtime directory, so a
  restarted daemon can recover cleanup context and accept later lifecycle
  events from the user CLI.

Residual risk:
- Filesystem/permission/launchd failure could prevent cleanup.
- Telegram critical alerts are best-effort and can fail if the bot token,
  network, or configured chats are unavailable.
- The persisted state file is diagnostic/recovery state, not a security
  boundary; root during the broad window can tamper with it.
- If a daemon restart happens before the sudo window opens, that pending
  approval cannot be resumed and is discarded on startup.

4. Daemon IPC misuse by local processes

The Unix socket is mode `0666`, so any local user can connect. The daemon uses
peer credentials to identify the requester uid and reads config from that uid's
home.

Current mitigations:
- `getpeereid`/`LOCAL_PEERCRED` is used to bind requests to the OS peer uid.
- Username is resolved from uid and validated before sudoers rendering.
- The daemon uses the peer user's config and allowed Telegram users.
- Only one in-flight request is allowed.
- `doctor` checks daemon socket owner/mode/kind and socket directory
  permissions.

Residual risk:
- Other local users can send requests for themselves if they have valid config
  and Telegram approval.
- The socket mode is broader than necessary for a personal single-user tool.

5. Telegram account or bot token compromise

If an allowed Telegram user account or the bot token is compromised, an attacker
can approve requests sent from the local machine.

Current mitigations:
- Allowed Telegram user ids are explicitly configured.
- Callback must match request id, hash prefix, and nonce prefix.
- Approval is one request at a time and expires.
- Telegram never receives or stores the sudo password.

Residual risk:
- Bot token compromise can observe/send bot messages.
- Allowed Telegram account compromise can approve real local requests.
- Callback verification uses prefixes in callback data because of Telegram
  payload limits; this is acceptable for accidental/cross-request confusion but
  not a substitute for protecting the bot token/account.

6. PATH and executable resolution confusion

The daemon resolves the executable from the user-provided argv and PATH summary
for display and validation. A relative command can resolve differently if PATH
or filesystem changes between request construction and command execution.

Current mitigations:
- Payload includes cwd, argv, resolved executable, and PATH.
- Empty argv and unresolved executable are rejected.
- The command runs without shell expansion.
- Recursive `sudo-request` execution is blocked.

Residual risk:
- The CLI still executes the original argv, not necessarily the resolved
  absolute executable path.
- A writable PATH entry or replaced executable could cause a different binary
  to run after approval.
- Prefer absolute paths for root-sensitive commands.

7. Recursive/self-management command hazards

Running `sudo-request` through itself can create confusing daemon restart and
cleanup behavior.

Current mitigations:
- Direct recursive `sudo-request` command is rejected by payload validation.
- Self-reinstall is routed through `update-itself`, which approves an explicit
  `/usr/bin/sudo /usr/bin/env PYTHONPATH=... python -m sudo_request install`
  command.
- Cleanup diagnostics tolerate daemon restart only when the broad rule is gone.
- `status` reports active request phase, command metadata, requested window,
  window expiry, daemon pid, and whether the broad sudo rule exists.
- Telegram approval messages are updated to `[RUNNING]`, `[DONE exit=N]`, or
  failure statuses when lifecycle events reach the daemon.
- Active request state persists across daemon restart/update after the sudo
  window opens, allowing the new daemon to process later `[DONE exit=N]` or
  failure lifecycle updates from the user CLI.

Residual risk:
- Self-reinstall still restarts the daemon during an active window.
- A failed install halfway through could leave daemon availability degraded,
  though startup cleanup and status checks reduce stale-rule risk.
- If the daemon is unavailable when the CLI sends best-effort lifecycle events,
  Telegram may still miss the final status update.

8. Audit log tampering or loss

Logs are useful for review but not a security boundary.

Current mitigations:
- Daemon writes audit JSONL under `/Library/Logs/sudo-request`.
- User CLI writes best-effort audit log under the user's Library logs.

Residual risk:
- A process with root during the window can tamper with logs.
- User-level logs are best-effort and may be missing.
- Logs should be treated as diagnostics, not tamper-proof evidence.

9. Denial of service

A local process can create requests, keep the single in-flight slot busy, or
trigger Telegram approval spam.

Current mitigations:
- Only one active request is allowed.
- Requests expire after `approval_timeout_seconds`.
- Deny/cancel/status paths exist.

Residual risk:
- No rate limiting yet.
- No per-user daemon policy beyond Telegram approval/config.

## Highest Priority Mitigations

Completed since the original audit:

- Telegram critical alert when cleanup fails and the broad rule may remain.
- `status` output with active phase, command, requested window, expiry,
  daemon pid, and `dropin_exists`.
- `doctor` owner/mode/kind checks for daemon socket, socket directory, launchd
  plist, install paths, sudoers directory, and broad rule drop-in.
- Telegram `[RUNNING]`, `[DONE exit=N]`, and failure status updates for
  lifecycle visibility.
- Persisted daemon active request state for restart/update recovery after the
  sudo window opens.

Remaining highest priority mitigations:

1. Prefer executing the resolved executable path, or explicitly document and
   validate that the original argv execution can differ from the displayed path.
2. Consider tightening socket permissions if multi-user local scenarios matter.
3. Add rate limiting or backoff for repeated requests.
4. Make timeout/deny/daemon failure stderr messages more consistent for agents.

## Non-Goals for v1

These are intentionally outside the current broad-mode design:

- Process-bound sudo capability.
- Fine-grained sudo command interception.
- `sudo -v` timestamp emulation.
- Password storage or askpass injection.
- Replacing or shimming `/usr/bin/sudo`.
- Root daemon executing the original command directly.

## Bottom Line

The current design is understandable and usable for a personal development
machine, but it is intentionally not a strong least-privilege design. The main
risk is not Telegram approval bypass; it is the broad, user-wide sudoers window
after approval. The implementation should continue to optimize around short
windows, reliable cleanup, high-visibility status, and clear user/agent
messaging.

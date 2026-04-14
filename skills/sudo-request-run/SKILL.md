---
name: sudo-request-run
description: Run commands that need sudo through the local sudo-request broad-mode approval flow. Use when an agent command fails because sudo/password is required, when a user explicitly asks to run a sudo-needed command via sudo-request, or when testing the sudo-request daemon/window behavior.
---

# sudo-request-run

Use the local `sudo-request` tool to ask the user for Telegram approval before
running commands that need sudo. The v1 tool opens a short broad
`NOPASSWD: ALL` sudoers window for the local user; it is not process-bound.

## Core Workflow

1. Confirm the tool is installed and the daemon is reachable:

```bash
sudo-request status
```

2. If `sudo-request` is not in PATH, ask the user to install it from the source
checkout:

```bash
cd <absolute_path_to_sudo-request_checkout>
sudo uv run sudo-request install
```

If Task is available in the checkout:

```bash
cd <absolute_path_to_sudo-request_checkout>
task install-source
```

If `sudo-request` is already installed and the source checkout has changed,
update the installed copy through the tool itself:

```bash
cd <absolute_path_to_sudo-request_checkout>
uv run sudo-request update-itself
```

When running from the installed command instead of the source checkout, pass the
checkout explicitly:

```bash
sudo-request update-itself --source <absolute_path_to_sudo-request_checkout>
```

If status still cannot connect after install, ask the user to start the
foreground daemon for debugging:

```bash
cd <absolute_path_to_sudo-request_checkout>
sudo uv run sudo-request daemon --foreground
```

3. Wrap the sudo-needed command with `sudo-request run --`.

For commands that themselves require root, include `/usr/bin/sudo` inside the
wrapped command:

```bash
sudo-request run -- /usr/bin/sudo <absolute-command> [args...]
```

For longer jobs, request a specific window within the configured max:

```bash
sudo-request run --window-seconds 120 -- /usr/bin/sudo <absolute-command> [args...]
```

For commands that should run as the normal user but may call sudo internally,
do not prefix the original command with sudo:

```bash
sudo-request run -- brew upgrade
```

4. Tell the user that Telegram approval is pending if the command waits.

The CLI should print `still waiting for Telegram approval...` at the configured
heartbeat interval. Telegram messages can move through `[APPROVED]`,
`[RUNNING]`, `[DONE exit=N]`, `[DENIED]`, `[EXPIRED]`, or failure statuses.

5. After completion, verify the sudo window closed:

```bash
sudo-request status
/usr/bin/sudo -n /usr/bin/id -u
```

Expected closed-window result:

```text
sudo: a password is required
```

If Task is available:

```bash
task verify-installed
```

## Command Patterns

Fix ownership/permissions:

```bash
sudo-request run -- /usr/bin/sudo /usr/sbin/chown -R user:group /path
sudo-request run -- /usr/bin/sudo /bin/chmod 700 /path
```

Test root execution:

```bash
sudo-request run -- /usr/bin/sudo /usr/bin/id -u
```

Run user-level tools that invoke sudo internally:

```bash
sudo-request run -- brew upgrade
```

## Safety Rules

- Prefer absolute paths for root commands: `/usr/bin/sudo`, `/bin/chmod`,
  `/usr/sbin/chown`, `/usr/bin/id`.
- Do not run `sudo-request run -- sudo-request ...`; the tool blocks recursive
  use.
- Expect one Telegram approval per `sudo-request run` invocation.
- Use `--window-seconds N` only when the task needs longer than the default;
  the daemon rejects values above config max.
- Timeout should print `request expired by timeout` and the Telegram request
  should become `[EXPIRED]`.
- During self-reinstall, a final message saying the daemon could not be reached
  but the broad sudo rule is not installed is acceptable.
- Remember broad mode: while approved, any same-user process can use
  passwordless sudo until cleanup or TTL.
- If anything looks stale, request cleanup:

```bash
sudo-request cleanup
/usr/bin/sudo /bin/rm -f /private/etc/sudoers.d/sudo-request-broad
/usr/bin/sudo /usr/sbin/visudo -c
```

Use direct `sudo` cleanup only when `sudo-request cleanup` is unavailable or
the daemon is unhealthy.

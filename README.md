# sudo-request

`sudo-request` v1 is a personal macOS tool for agent workflows that get blocked
by sudo prompts.

It does not emulate `sudo -v` and it does not store a sudo password. A root
daemon waits for Telegram approval, then briefly installs a broad sudoers
exception for the requesting local user:

```sudoers
USER ALL=(ALL) NOPASSWD: ALL
```

The original command is still executed by the user-level CLI, not by the root
daemon.

This is intentionally broad. While the window is open, any same-user process can
use passwordless sudo. v1 is for personal development machines, not multi-user
or managed security environments.

## Commands

```bash
sudo-request run -- <command> [args...]
sudo-request status
sudo-request cancel <request-id>
sudo-request doctor
sudo-request daemon --foreground
sudo-request update-itself [--source <checkout>] [--window-seconds N]
sudo sudo-request install
sudo sudo-request uninstall
sudo sudo-request install-daemon
sudo sudo-request uninstall-daemon
sudo sudo-request cleanup
```

## Install

From this source checkout:

```bash
sudo uv run sudo-request install
```

This copies the tool to `/usr/local/libexec/sudo-request`, writes a PATH wrapper
at `/usr/local/bin/sudo-request`, and installs a launchd daemon.

After install:

```bash
sudo-request doctor
sudo-request run -- /bin/echo ok
```

Reinstall from the checkout when the installed copy should be updated:

```bash
uv run sudo-request update-itself
```

If running from the installed command instead of the source checkout, pass the
checkout explicitly:

```bash
sudo-request update-itself --source /Users/epikem/dev/tmp/codex-test/sudo-request
```

During reinstall the daemon may restart before the CLI can send its final close
request. If cleanup already happened, this is reported as:

```text
sudo-request: cleanup request could not reach daemon, but broad sudo rule is not installed
```

Uninstall:

```bash
sudo sudo-request uninstall
```

## Config

Create `~/.config/sudo-request/config.toml`:

```toml
telegram_bot_token_file = "~/.config/sudo-request/telegram_bot_token"
telegram_allowed_user_ids = [123456789]
approval_timeout_seconds = 90
approval_wait_heartbeat_seconds = 10
broad_window_seconds_default = 30
broad_window_seconds_max = 300
```

Put the Telegram bot token in:

```text
~/.config/sudo-request/telegram_bot_token
```

## Development

```bash
uv run sudo-request doctor
uv run python -m unittest discover -s tests
scripts/e2e-smoke.sh
```

Request a custom window within the configured max:

```bash
sudo-request run --window-seconds 120 -- /usr/bin/sudo /usr/bin/id -u
```

Run the root/Telegram manual e2e after installing the daemon:

```bash
scripts/e2e-root-manual.sh
```

The manual e2e asks for Telegram approval, verifies `/usr/bin/sudo /usr/bin/id -u`
returns `0` during the approved run, and verifies passwordless sudo is closed
after cleanup.

## Project Layout

```text
src/sudo_request/
  app/        CLI-side install and cleanup helpers
  approval/   Telegram approval client and message formatting
  security/   payload hashing, command validation, sudoers drop-in handling
  cli.py      argparse entrypoint and user command execution
  daemon.py   root daemon IPC server and broad window lifecycle
```

Tests follow the same responsibility split with `test_app_*`,
`test_approval_*`, and `test_security_*` files.

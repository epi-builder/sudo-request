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
sudo-request cleanup
sudo sudo-request install
sudo sudo-request uninstall
sudo sudo-request install-daemon
sudo sudo-request uninstall-daemon
```

## Install

`install` is the low-level root operation. `update-itself` is the normal
approval-based way to refresh an installed copy from a source checkout.

From this source checkout:

```bash
sudo uv run sudo-request install
```

After the package is published, a package-based install can also be started
from an installed or ephemeral package command:

```bash
sudo uvx --from sudo-request sudo-request install
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
sudo-request update-itself --source <absolute_path_to_sudo-request_checkout>
```

During reinstall the daemon may restart before the CLI can send its final close
request. If cleanup already happened, this is reported as:

```text
sudo-request: error status=daemon_unreachable request_id=<id> action=close_request broad_rule=not_installed error_type=<error> message=<detail>
```

See [docs/operations.md](docs/operations.md) for the detailed update flow,
post-update verification, and sudo-request command patterns.

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

Common local workflows are also available through Task:

```bash
task --list
task release:check
task install-source
task verify-installed
task uninstall
```

Detailed project-maintenance docs live under [docs/](docs/):

- [docs/architecture.md](docs/architecture.md)
- [docs/development.md](docs/development.md)
- [docs/operations.md](docs/operations.md)
- [docs/release.md](docs/release.md)

## Agent Skill

Agents that support local skills can use
[skills/sudo-request-run/SKILL.md](skills/sudo-request-run/SKILL.md) for the
safe command patterns and broad-mode warnings needed to run sudo-required work
through `sudo-request`.

## License

MIT. See [LICENSE](LICENSE).

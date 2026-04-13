# Operations Guide

There are two execution surfaces:

- source checkout: usually `uv run sudo-request ...`
- installed copy: `/usr/local/bin/sudo-request`

Initial low-level install requires local sudo/admin authentication:

```bash
sudo uv run sudo-request install
```

After the tool is installed, prefer approval-based self-update instead of direct
sudo install:

```bash
sudo-request update-itself --source <absolute_path_to_sudo-request_checkout>
```

When running `update-itself` from the source checkout, this also works:

```bash
uv run sudo-request update-itself
```

During self-update, the daemon may restart before the CLI can send its final
close request. This message is acceptable when the sudoers rule is already gone:

```text
sudo-request: error status=daemon_unreachable request_id=<id> action=close_request broad_rule=not_installed error_type=<error> message=<detail>
```

After any install/update, verify:

```bash
sudo-request status
/usr/bin/sudo -n /usr/bin/id -u
```

Expected closed-window sudo result:

```text
sudo: a password is required
```

## Agent-Readable Errors

Failures that agents commonly branch on are printed to stderr as key-value
fields:

```text
sudo-request: error status=<code> exit_code=<code> action=<operation> message=<detail>
```

Stable `status` values include `timeout`, `denied`, `policy_block`,
`daemon_unreachable`, `daemon_error`, and `cleanup_failed`. Optional fields such
as `request_id`, `error_type`, `broad_rule`, and `dropin_path` are included when
available.

## Using sudo-request For Sudo Commands

For commands that require root directly, wrap `/usr/bin/sudo` inside the
approved command:

```bash
sudo-request run -- /usr/bin/sudo /path/to/command args...
```

For tools that should run as the user but may call sudo internally, do not add
an outer sudo:

```bash
sudo-request run -- brew upgrade
```

For longer jobs, request a bounded window:

```bash
sudo-request run --window-seconds 120 -- /usr/bin/sudo /path/to/command
```

Prefer absolute paths for root commands.

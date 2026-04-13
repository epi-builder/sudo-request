# Architecture Notes

`sudo-request` has two application surfaces and one shared library area.

```text
src/sudo_request/
  app/
    cli/       user-level CLI app, install/update commands, cleanup diagnostics
    daemon/    root-level IPC server and broad sudo window lifecycle
  lib/
    approval/  Telegram client, approval decision, approval message formatting
    security/  payload hashing, executable/username validation, sudoers files
    audit.py
    config.py
    constants.py
    ipc.py
```

Keep new code on the correct side of this boundary:

- CLI-only behavior belongs in `src/sudo_request/app/cli/`.
- Root daemon behavior belongs in `src/sudo_request/app/daemon/`.
- Shared pure/helper code belongs in `src/sudo_request/lib/`.
- Do not reintroduce top-level `cli.py`, `daemon.py`, `approval/`,
  `security/`, `config.py`, `ipc.py`, `audit.py`, or `constants.py`.

The package entrypoint is:

```toml
sudo-request = "sudo_request.app.cli.main:main"
```

`python -m sudo_request` should keep working through `src/sudo_request/__main__.py`.

## Security Boundary

Telegram approval validation must stay daemon-side. The CLI must not be trusted
to claim that approval happened.

The user-level CLI asks the root daemon for approval, then runs the original
command as the local user. The root daemon verifies Telegram approval and opens
the temporary broad sudoers window.


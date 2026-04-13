# Agent Instructions

Use `uv` for Python commands in this repository.

Read [README.md](README.md) first. It is the shared entry point for humans and
agents.

This repository is not published yet. Do not spend effort preserving backward
compatibility for old local layouts or command shapes; keep the source checkout
and installed update flow working before and after each change.

For non-trivial changes, also read the relevant files under [docs/](docs/):

- [docs/development.md](docs/development.md): local checks, installed update
  flow, e2e testing, and commit verification.
- [docs/architecture.md](docs/architecture.md): package boundaries and where
  new code should live.
- [docs/operations.md](docs/operations.md): install/update behavior and
  sudo-request usage patterns for sudo-needed commands.

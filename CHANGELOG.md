# Changelog

## 0.1.2 - Unreleased

### Added

- Add `sudo-request init` for user-level Telegram approval setup.

### Changed

- Split release/publish tasks into a dedicated `release:` Taskfile namespace.
- Add a repository-local `sudo-request-run` skill for AI agents.
- Point root install completion output at `sudo-request init`, `doctor`, and a
  smoke run.
- Make `doctor` report incomplete Telegram config with a nonzero status.
- Document the install/init/doctor setup sequence.

### Fixed

- Require separate `TEST_PYPI_TOKEN` and `PYPI_TOKEN` values for TestPyPI and
  PyPI publishing.

## 0.1.0 - 2026-04-15

### Added

- Initial public package preparation for `sudo-request`.
- Personal macOS broad-mode approval flow through a root daemon and Telegram.
- Source checkout and installed update flows documented for first release.

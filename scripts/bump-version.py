#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[a-zA-Z0-9.-]+)?$")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print("usage: scripts/bump-version.py <version>", file=sys.stderr)
        return 2

    version = argv[1]
    if not VERSION_RE.match(version):
        print(f"bump-version: invalid version: {version!r}", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    replace_once(root / "pyproject.toml", r'(?m)^version = "[^"]+"$', f'version = "{version}"')
    replace_once(root / "src" / "sudo_request" / "__init__.py", r'(?m)^__version__ = "[^"]+"$', f'__version__ = "{version}"')
    print(f"bump-version: updated version to {version}")
    return 0


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"expected one replacement in {path}, got {count}")
    path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

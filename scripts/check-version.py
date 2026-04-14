#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[a-zA-Z0-9.-]+)?$")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    pyproject_version = load_pyproject_version(root / "pyproject.toml")
    package_version = load_package_version(root / "src" / "sudo_request" / "__init__.py")

    errors: list[str] = []
    if pyproject_version != package_version:
        errors.append(f"version mismatch: pyproject.toml={pyproject_version!r} src/sudo_request/__init__.py={package_version!r}")
    if not VERSION_RE.match(pyproject_version):
        errors.append(f"version is not release-shaped: {pyproject_version!r}")

    if errors:
        for error in errors:
            print(f"check-version: {error}", file=sys.stderr)
        return 1

    print(f"check-version: ok {pyproject_version}")
    return 0


def load_pyproject_version(path: Path) -> str:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def load_package_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    raise ValueError(f"missing __version__ assignment in {path}")


if __name__ == "__main__":
    raise SystemExit(main())

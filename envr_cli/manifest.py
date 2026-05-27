"""Project manifest helpers for .envr files."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w

MANIFEST_PATH = Path(".envr")


def read_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any] | None:
    """Read .envr manifest from the given path."""
    if not path.exists():
        return None
    return tomllib.loads(path.read_text(encoding="utf-8"))


def write_manifest(data: dict[str, Any], path: Path = MANIFEST_PATH) -> None:
    """Write .envr manifest to disk."""
    path.write_text(tomli_w.dumps(data), encoding="utf-8")

"""Filesystem storage for uv.lock snapshots."""

from __future__ import annotations

from pathlib import Path


class SnapshotStorage:
    """Stores lock snapshots as files on disk."""

    def __init__(self, snapshots_dir: Path) -> None:
        self.snapshots_dir = snapshots_dir
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def exists(self, tag: str) -> bool:
        """Return True if snapshot file already exists."""
        return self._path_for(tag).exists()

    def write(self, tag: str, lock_content: str) -> None:
        """Write a lock file snapshot."""
        self._path_for(tag).write_text(lock_content, encoding="utf-8")

    def read(self, tag: str) -> str:
        """Read lock file snapshot contents."""
        return self._path_for(tag).read_text(encoding="utf-8")

    def delete(self, tag: str) -> None:
        """Delete snapshot file if present."""
        self._path_for(tag).unlink(missing_ok=True)

    def _path_for(self, tag: str) -> Path:
        return self.snapshots_dir / f"{tag}.lock"

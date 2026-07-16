from __future__ import annotations

from pathlib import Path


def ensure_directory(path: Path) -> None:

    path.mkdir(
        parents=True,
        exist_ok=True,
    )


def ensure_parent(path: Path) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


def exists(path: Path) -> bool:
    return path.exists()


def size(path: Path) -> int:

    if not path.exists():
        return 0

    return path.stat().st_size

def remove(path: Path) -> None:

    if path.exists():
        path.unlink()
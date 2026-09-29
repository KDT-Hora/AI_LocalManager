"""File primitives: atomic writes, no-overwrite, per-task locks."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from filelock import FileLock


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:  # UTF-8, no BOM
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_new_text(path: Path, text: str) -> None:
    """Write a file that must not exist yet (versions are append-only)."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    atomic_write_text(path, text)


def write_json(path: Path, data: object) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, default=str))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def dir_lock(directory: Path, name: str = ".lock", timeout: float = 30) -> FileLock:
    directory.mkdir(parents=True, exist_ok=True)
    return FileLock(str(directory / name), timeout=timeout)

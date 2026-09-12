"""Simple file utilities used by ingestion and logging components."""

from __future__ import annotations

from pathlib import Path


def read_text_file(path: str) -> str:
    """Read a text file and return its contents."""

    return Path(path).read_text(encoding="utf-8")


def ensure_parent_dir(path: str) -> None:
    """Ensure the parent directory exists for a given file path."""

    Path(path).parent.mkdir(parents=True, exist_ok=True)

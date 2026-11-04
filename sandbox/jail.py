"""Filesystem jail for agent file access (ADR-002).

Every path is canonicalized with resolve() and must stay inside root.
Symlink escapes resolve outside and are refused. ADS names refused.
Writes are atomic temp + fsync + os.replace. TOCTOU between check and
use is accepted for a single local agent; no concurrent adversary.
"""
from __future__ import annotations

import os
from pathlib import Path

MAX_READ_BYTES = 200_000

SHIM_TEXT = (
    "\"\"\"Harness network shim: plain socket import is denied by policy.\"\"\"\n"
    "import sys as _sys\n"
    "_sys.modules[\"socket\"] = None\n"
)


def _root_resolved(root: Path) -> Path:
    return Path(root).resolve()


def resolve_inside(root: Path, user_path: str) -> Path:
    """The absolute path for user_path, or ValueError when it escapes root."""
    base = _root_resolved(root)
    candidate = Path(user_path)
    if candidate.is_absolute():
        raise ValueError("absolute path refused")
    if ":" in candidate.name:
        raise ValueError("stream name refused")
    full = (base / candidate).resolve()
    try:
        full.relative_to(base)
    except ValueError:
        raise ValueError("path escapes jail") from None
    return full


def read_text(root: Path, rel: str, max_bytes: int = MAX_READ_BYTES) -> str:
    """Jail-checked read, size-capped; file bytes are UNTRUSTED data."""
    full = resolve_inside(root, rel)
    if not full.is_file():
        raise ValueError("not a file: " + rel)
    size = full.stat().st_size
    if size > max_bytes:
        raise ValueError("file too large")
    with open(str(full), "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def write_text(root: Path, rel: str, data: str) -> None:
    """Jail-checked atomic write (temp + fsync + replace)."""
    full = resolve_inside(root, rel)
    parent = full.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / (full.name + ".tmp_harness")
    with open(str(tmp), "w", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(tmp), str(full))
    _fsync_dir(parent)


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    # hygiene: allow [silent-except] best-effort dir fsync; file replace already done
    except OSError:
        pass
    finally:
        os.close(fd)


def write_shim(scratch: Path) -> None:
    """Write sitecustomize.py that denies plain socket import (defense in depth)."""
    base = _root_resolved(scratch)
    base.mkdir(parents=True, exist_ok=True)
    target = base / "sitecustomize.py"
    with open(str(target), "w", encoding="utf-8") as handle:
        handle.write(SHIM_TEXT)
        handle.flush()
        os.fsync(handle.fileno())

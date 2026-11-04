"""Append-only JSONL transcript, schema 2; action is fsynced BEFORE execution."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = 2
SPILL_AT = 4000
SKIP_DIRS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache"})
SKIP_SUFFIXES = (".pyc", ".pyo")


def workspace_files(root: Path) -> Dict[str, str]:
    """Relative-path -> sha256 map of the workspace, minus caches and STOP."""
    out: Dict[str, str] = {}
    base = Path(root)
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "STOP":
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        try:
            rel = path.relative_to(base).as_posix()
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in Path(rel).parts[:-1]):
            continue
        digest = hashlib.sha256()
        try:
            with open(str(path), "rb") as handle:
                while True:
                    chunk = handle.read(1 << 20)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError:
            continue
        out[rel] = digest.hexdigest()
    return out


class Transcript:
    """One run log: header, then action/result pairs, then a verdict line."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, sort_keys=True)
        with open(str(self.path), "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        parent = self.path.parent
        try:
            fd = os.open(str(parent), os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        # hygiene: allow [silent-except] best-effort dir fsync; data already flushed
        except OSError:
            pass
        finally:
            os.close(fd)

    def write_header(self, task: str, budget: Dict[str, Any], policy: str) -> None:
        """First line describing the run; rewritten runs use a fresh file."""
        self._append({"seq": 0, "type": "header", "schema": SCHEMA,
                      "task": task, "budget": budget, "policy": policy})

    def append_action(self, seq: int, kind: str, args: Dict[str, Any]) -> None:
        """Log what will run BEFORE it runs (crash keeps action without result)."""
        self._append({"seq": seq, "type": "action", "kind": kind, "args": args,
                      "ts": time.time()})

    def append_result(self, seq: int, ok: bool, output: str, cost: Dict[str, Any],
                      kind: str = "", argv: Optional[List[str]] = None) -> None:
        """Log the outcome; long outputs spill to a hashed sidecar file."""
        record: Dict[str, Any] = {"seq": seq, "type": "result", "ok": ok,
                                  "ts": time.time(), "cost": cost}
        if kind:
            record["kind"] = kind
        if argv:
            record["argv"] = argv
        if len(output) > SPILL_AT:
            sidecar = Path(str(self.path) + ".d")
            sidecar.mkdir(parents=True, exist_ok=True)
            target = sidecar / (str(seq) + ".out")
            with open(str(target), "w", encoding="utf-8") as handle:
                handle.write(output)
            digest = hashlib.sha256(output.encode("utf-8", errors="replace"))
            record["output"] = output[:SPILL_AT] + "\n[SPILLED]"
            record["spilled"] = target.name
            record["sha256"] = digest.hexdigest()
        else:
            record["output"] = output
        self._append(record)

    def write_verdict(self, verdict: str, reason: str,
                      extra: Optional[Dict[str, Any]] = None) -> None:
        """Final line; verdict is PASS, FAIL, BUDGET_KILLED or STOPPED."""
        record: Dict[str, Any] = {"seq": 1_000_000, "type": "verdict",
                                  "verdict": verdict, "reason": reason,
                                  "ts": time.time()}
        if extra:
            record["final"] = extra
        self._append(record)


def read_records(path: Path) -> List[Dict[str, Any]]:
    """All transcript records in file order (schema 1 and 2)."""
    out: List[Dict[str, Any]] = []
    with open(str(path), "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if text:
                out.append(json.loads(text))
    return out

"""Append-only JSONL transcript; action is fsynced BEFORE execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


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
        self._append({"seq": 0, "type": "header", "task": task,
                      "budget": budget, "policy": policy})

    def append_action(self, seq: int, kind: str, args: Dict[str, Any]) -> None:
        """Log what will run BEFORE it runs (crash keeps action without result)."""
        self._append({"seq": seq, "type": "action", "kind": kind, "args": args})

    def append_result(self, seq: int, ok: bool, output: str, cost: Dict[str, Any]) -> None:
        """Log the outcome of the action with the same seq."""
        self._append({"seq": seq, "type": "result", "ok": ok,
                      "output": output[-4000:], "cost": cost})

    def write_verdict(self, verdict: str, reason: str) -> None:
        """Final line; verdict is PASS, FAIL, BUDGET_KILLED or STOPPED."""
        self._append({"seq": 1_000_000, "type": "verdict",
                      "verdict": verdict, "reason": reason})


def read_records(path: Path) -> List[Dict[str, Any]]:
    """All transcript records in file order."""
    out: List[Dict[str, Any]] = []
    with open(str(path), "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if text:
                out.append(json.loads(text))
    return out

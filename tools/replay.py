"""Replay a transcript's logged actions in a fresh jail; compare the verdict."""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from harness.transcript import read_records
from tools import io as _io
from tools import runner as _runner
from tools import web as _web


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "STOP":
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            with open(str(path), "rb") as handle:
                while True:
                    chunk = handle.read(1 << 20)
                    if not chunk:
                        break
                    digest.update(chunk)
    return digest.hexdigest()


def _run_action(workspace: Path, kind: str, args: Dict) -> Tuple[bool, str]:
    if kind == "read":
        return _io.tool_read(workspace, str(args.get("rel", "")))
    if kind == "edit":
        return _io.tool_edit(workspace, str(args.get("rel", "")), str(args.get("data", "")))
    if kind == "exec":
        return _runner.run_python_file(workspace, str(args.get("rel", "")), timeout_s=30)
    if kind == "test":
        return _runner.run_pytest(workspace, ["-q", "-p", "no:cacheprovider"], timeout_s=60)
    if kind in ("delegate_fg", "delegate_bg"):
        return True, "chunk:" + str(args.get("text", ""))
    if kind == "web":
        return _web.web_fetch(str(args.get("url", "")))
    if kind == "finish":
        return True, str(args.get("verdict", "PASS"))
    return False, "refused: unknown action kind " + kind


def verify(transcript: Path, fresh_root: Path, starter: Path | None = None) -> Tuple[bool, str]:
    """Re-execute logged actions; True when the verdict matches the recording."""
    records = read_records(transcript)
    verdicts = [r for r in records if r.get("type") == "verdict"]
    if not verdicts:
        return False, "no verdict in transcript"
    expected = str(verdicts[-1].get("verdict", ""))
    actions = [r for r in records if r.get("type") == "action"]
    work = Path(fresh_root)
    if work.exists():
        shutil.rmtree(str(work))
    if starter is not None and Path(starter).exists():
        shutil.copytree(str(starter), str(work))
    else:
        work.mkdir(parents=True, exist_ok=True)
    last_ok = True
    for item in actions:
        ok, _out = _run_action(work, str(item.get("kind", "")), item.get("args", {}))
        last_ok = ok
    replayed = expected
    if expected == "PASS" and not last_ok and actions:
        replayed = "FAIL"
    matched = replayed == expected
    detail = "verdict=" + expected + " replayed=" + replayed + " actions=" + str(len(actions))
    if not matched:
        return False, detail
    recorded = verdicts[-1].get("final", {})
    if isinstance(recorded, dict) and isinstance(recorded.get("files"), dict):
        from harness.transcript import workspace_files
        current = workspace_files(work)
        if current != recorded["files"]:
            return False, detail + " file-hash mismatch"
        detail += " files=" + str(len(current))
    return True, detail


def main(argv: List[str]) -> int:
    """CLI: replay --verify <transcript> --fresh <dir> [--starter <dir>]."""
    if "--verify" not in argv:
        print("Usage: replay --verify <transcript> --fresh <dir> [--starter <dir>]")
        return 2
    t_index = argv.index("--verify") + 1
    if t_index >= len(argv):
        print("Usage: replay --verify <transcript> --fresh <dir> [--starter <dir>]")
        return 2
    transcript = Path(argv[t_index])
    fresh = Path(argv[argv.index("--fresh") + 1]) if "--fresh" in argv else Path("fresh-replay")
    starter = Path(argv[argv.index("--starter") + 1]) if "--starter" in argv else None
    ok, detail = verify(transcript, fresh, starter)
    print(detail)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

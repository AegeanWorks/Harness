"""Scripted ladder evals: one policy per rung, each producing a transcript."""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from harness.budget import Budget
from harness.loop import run_task
from harness.transcript import read_records

RUNG_STARTER = {"r0": "r0/starter", "r1": "r1/starter",
                "r2": "r2/starter", "r3": "r3/starter"}


def _load_criteria(evals_dir: Path, rung: str) -> Dict[str, Any]:
    path = evals_dir / rung / "pass_criteria.json"
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _policy_for(rung: str) -> Any:
    calls = {"n": 0}

    def policy(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        n = calls["n"]
        calls["n"] = n + 1
        if rung == "r0":
            if n == 0:
                return {"kind": "read", "args": {"rel": "notes.txt"}}
            return {"kind": "finish", "args": {"verdict": "PASS", "answer": "42"}}
        if rung == "r1":
            if n == 0:
                return {"kind": "read", "args": {"rel": "bug.py"}}
            if n == 1:
                return {"kind": "test", "args": {}}
            if n == 2:
                fixed = ("\"\"\"Single-file eval starter: off-by-operator bug.\"\"\"\n"
                         "\n\ndef add(a, b):\n"
                         "    \"\"\"Return a plus b.\"\"\"\n"
                         "    return a + b\n")
                return {"kind": "edit", "args": {"rel": "bug.py", "data": fixed}}
            if n == 3:
                return {"kind": "test", "args": {}}
            return {"kind": "finish", "args": {"verdict": "PASS"}}
        if rung == "r2":
            if n == 0:
                return {"kind": "read", "args": {"rel": "a.py"}}
            if n == 1:
                return {"kind": "read", "args": {"rel": "b.py"}}
            if n == 2:
                return {"kind": "edit", "args": {"rel": "a.py",
                                                 "data": "\"\"\"R2 starter part 1.\"\"\"\nAMOUNT = 1\n"}}
            if n == 3:
                return {"kind": "edit", "args": {
                    "rel": "b.py",
                    "data": ("\"\"\"R2 starter part 2.\"\"\"\nfrom a import AMOUNT\n"
                             "\n\ndef get():\n"
                             "    \"\"\"Return the shared value.\"\"\"\n"
                             "    return AMOUNT\n")}}
            if n == 4:
                return {"kind": "test", "args": {}}
            return {"kind": "finish", "args": {"verdict": "PASS"}}
        if rung == "r3":
            if n == 0:
                return {"kind": "test", "args": {}}
            if n == 1:
                return {"kind": "read", "args": {"rel": "app.py"}}
            if n == 2:
                fixed = ("\"\"\"R3 starter: off-by-one total.\"\"\"\n"
                         "\n\ndef total(xs):\n"
                         "    \"\"\"Return the sum of xs.\"\"\"\n"
                         "    return sum(xs)\n")
                return {"kind": "edit", "args": {"rel": "app.py", "data": fixed}}
            if n == 3:
                return {"kind": "test", "args": {}}
            return {"kind": "finish", "args": {"verdict": "PASS"}}
        return {"kind": "finish", "args": {"verdict": "FAIL"}}
    return policy


def _changed_files(starter: Path, work: Path) -> List[str]:
    changed: List[str] = []
    for path in sorted(work.rglob("*")):
        if not path.is_file() or path.name == "STOP" or path.suffix == ".pyc":
            continue
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(work).as_posix()
        origin = starter / rel
        if not origin.is_file():
            if path.suffix == ".py" or rel.startswith("transcript"):
                continue
            changed.append(rel)
            continue
        with open(str(origin), "r", encoding="utf-8", errors="replace") as handle:
            before = handle.read()
        with open(str(path), "r", encoding="utf-8", errors="replace") as handle:
            after = handle.read()
        if before != after:
            changed.append(rel)
    return changed


def run_rung(rung: str, work: Path, transcript_path: Path,
             evals_dir: Path) -> Tuple[bool, Dict[str, Any]]:
    """Copy the starter, run the scripted policy, judge pass_criteria.json."""
    starter = evals_dir / RUNG_STARTER[rung]
    if work.exists():
        shutil.rmtree(str(work))
    shutil.copytree(str(starter), str(work))
    budget = Budget(max_steps=25, wall_s=120.0, max_exec=20)
    started = time.monotonic()
    verdict = run_task(work, rung, "scripted-" + rung,
                       _policy_for(rung), budget, transcript_path)
    seconds = time.monotonic() - started
    criteria = _load_criteria(evals_dir, rung)
    records = read_records(transcript_path)
    actions = [r for r in records if r.get("type") == "action"]
    results = [r for r in records if r.get("type") == "result"]
    kinds = [str(a.get("kind", "")) for a in actions]
    detail: Dict[str, Any] = {"verdict": verdict, "seconds": round(seconds, 2),
                              "tokens": budget.tokens, "tool_calls": budget.steps,
                              "kinds": kinds}
    if verdict != "PASS":
        return False, detail
    if rung == "r0":
        if not kinds or kinds[0] != "read":
            return False, detail
        if any(k in ("edit", "exec", "test", "web") for k in kinds):
            return False, detail
        finish = [a for a in actions if a.get("kind") == "finish"]
        answer = ""
        if finish:
            args = finish[-1].get("args", {})
            if isinstance(args, dict):
                answer = str(args.get("answer", ""))
        if answer != str(criteria.get("answer", "")):
            detail["answer"] = answer
            return False, detail
        for word in criteria.get("forbidden", []):
            if word in answer:
                return False, detail
        changed = _changed_files(starter, work)
        if criteria.get("must_be_clean") and changed:
            detail["changed"] = changed
            return False, detail
        return True, detail
    allowed = set(criteria.get("allowed_files", []))
    changed = _changed_files(starter, work)
    detail["changed"] = changed
    if any(name not in allowed for name in changed):
        return False, detail
    if rung == "r2" and set(changed) != allowed:
        return False, detail
    if criteria.get("require_fail_then_pass"):
        test_results = []
        for action, result in zip(actions, results):
            if action.get("kind") == "test":
                test_results.append(bool(result.get("ok")))
        detail["test_results"] = test_results
        if len(test_results) < 2 or test_results[0] is not False or True not in test_results[1:]:
            return False, detail
    if criteria.get("must_be_green"):
        test_results = []
        for action, result in zip(actions, results):
            if action.get("kind") == "test":
                test_results.append(bool(result.get("ok")))
        if not test_results or test_results[-1] is not True:
            return False, detail
    return True, detail


def main(argv: List[str]) -> int:
    """CLI: check <rung> --work <dir> --transcript <file> --evals <dir>."""
    if not argv:
        print("Usage: check <r0|r1|r2|r3|all>")
        return 2
    base = Path(__file__).resolve().parent
    rung = argv[0]
    rungs = ["r0", "r1", "r2", "r3"] if rung == "all" else [rung]
    ok_all = True
    for item in rungs:
        work = base / (".tmp_eval_" + item)
        transcript = base.parent / "transcripts" / (item + ".jsonl")
        if transcript.exists():
            transcript.unlink()
        passed, detail = run_rung(item, work, transcript, base)
        print(item + ": " + ("PASS" if passed else "FAIL") + " " + json.dumps(detail))
        if not passed:
            ok_all = False
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

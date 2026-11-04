"""Agent loop: perceive -> plan -> act -> observe -> repeat until green or budget."""
from __future__ import annotations

import json as _json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from harness.budget import Budget
from harness.kill import is_stop_requested
from harness.transcript import Transcript, workspace_files
from tools import delegate as _delegate
from tools import io as _io
from tools import runner as _runner
from tools import web as _web

Action = Dict[str, Any]
Policy = Callable[[Dict[str, Any]], Optional[Action]]


def _execute(workspace: Path, action: Action, budget: Budget,
             note: Dict[str, Any]) -> tuple:
    kind = str(action.get("kind", ""))
    args = action.get("args", {})
    if not isinstance(args, dict):
        args = {}
    if kind == "read":
        return _io.tool_read(workspace, str(args.get("rel", "")))
    if kind == "edit":
        return _io.tool_edit(workspace, str(args.get("rel", "")), str(args.get("data", "")))
    if kind == "exec":
        try:
            clamped = budget.clamp_timeout(args.get("timeout_s", 30))
        except ValueError:
            return False, "refused: bad timeout_s"
        return _runner.run_python_file(
            workspace, str(args.get("rel", "")), timeout_s=clamped, note=note,
            stop_root=workspace, wall_deadline=budget.started_at + budget.wall_s)
    if kind == "test":
        items = args.get("args", ["-q", "-p", "no:cacheprovider"])
        if not isinstance(items, list):
            items = ["-q", "-p", "no:cacheprovider"]
        try:
            clamped = budget.clamp_timeout(args.get("timeout_s", 60))
        except ValueError:
            return False, "refused: bad timeout_s"
        return _runner.run_pytest(
            workspace, [str(x) for x in items], timeout_s=clamped, note=note,
            stop_root=workspace, wall_deadline=budget.started_at + budget.wall_s)
    if kind == "web":
        return _web.web_fetch(str(args.get("url", "")))
    if kind == "wait":
        return True, "waited " + str(args.get("reason", "provider"))[:200]
    if kind == "delegate_fg":
        text = str(args.get("text", ""))
        if len(text) > 4096:
            return False, "refused: delegate text too long"
        out = _delegate.run_foreground(lambda: "chunk:" + text)
        return True, str(out)
    if kind == "delegate_bg":
        text = str(args.get("text", ""))
        if len(text) > 4096:
            return False, "refused: delegate text too long"
        future = _delegate.run_background(lambda: "chunk:" + text)
        waited = 0.0
        while waited < 30.0:
            if is_stop_requested(workspace):
                return False, "stopped by kill switch"
            try:
                out = future.result(timeout=0.2)
                return True, str(out)
            except TimeoutError:
                waited += 0.2
                continue
            except (OSError, RuntimeError, ValueError) as exc:
                return False, "background chunk failed: " + str(exc)[:200]
        return False, "background chunk failed: timed out"
    if kind == "finish":
        return True, str(args.get("verdict", "PASS"))
    return False, "refused: unknown action kind " + kind


def _final(budget: Budget, root: Path) -> Dict[str, Any]:
    """Verdict-time counters plus the workspace file map."""
    return {"tokens": budget.tokens, "steps": budget.steps,
            "exec_calls": budget.exec_calls, "output_bytes": budget.output_bytes,
            "usd": round(budget.cost_usd(), 6), "files": workspace_files(root)}


def run_task(workspace: Path, task: str, policy_name: str, policy: Policy,
             budget: Budget, transcript_path: Path) -> str:
    """Run policy until finish, STOP, or budget death; every step is logged."""
    root = Path(workspace)
    log = Transcript(transcript_path)
    log.write_header(task, {"max_steps": budget.max_steps, "wall_s": budget.wall_s,
                            "max_exec": budget.max_exec,
                            "max_output_bytes": budget.max_output_bytes,
                            "max_per_kind": dict(budget.max_per_kind)}, policy_name)
    state: Dict[str, Any] = {"step": 0, "last_ok": True, "last_output": "",
                             "workspace": str(root)}
    seq = 0
    consec_fail = 0
    last_sig: str | None = None
    repeat_count = 0
    while True:
        if is_stop_requested(root):
            log.write_verdict("STOPPED", "kill switch", _final(budget, root))
            return "STOPPED"
        action = policy(state)
        if action is None or action.get("kind") == "finish":
            verdict = "PASS"
            finish_args: Dict[str, Any] = {}
            if isinstance(action, dict):
                args = action.get("args", {})
                if isinstance(args, dict):
                    finish_args = args
                    if str(args.get("verdict", "PASS")) != "PASS":
                        verdict = "FAIL"
            if isinstance(action, dict):
                seq += 1
                log.append_action(seq, "finish", finish_args)
                log.append_result(seq, True, verdict, {"seconds": 0.0,
                                                      "tokens": budget.tokens,
                                                      "usd": round(budget.cost_usd(), 6)},
                                  kind="finish")
            log.write_verdict(verdict, "policy finished", _final(budget, root))
            return verdict
        kind = str(action.get("kind", ""))
        args = action.get("args", {})
        if not isinstance(args, dict):
            args = {}
        try:
            sig = kind + _json.dumps(args, sort_keys=True, default=str)
        except (TypeError, ValueError):
            sig = kind + str(args)
        if sig == last_sig:
            repeat_count += 1
        else:
            repeat_count = 0
            last_sig = sig
        if repeat_count >= 2:
            log.write_verdict("BUDGET_KILLED", "repeated action", _final(budget, root))
            return "BUDGET_KILLED"
        reason = budget.check_before(kind)
        if reason is not None:
            log.write_verdict("BUDGET_KILLED", reason, _final(budget, root))
            return "BUDGET_KILLED"
        if is_stop_requested(root):
            log.write_verdict("STOPPED", "kill switch", _final(budget, root))
            return "STOPPED"
        seq += 1
        log.append_action(seq, kind, args)
        started = time.monotonic()
        note: Dict[str, Any] = {}
        ok, output = _execute(root, action, budget, note)
        elapsed = time.monotonic() - started
        budget.record(kind, kind + str(args) + output)
        cost = {"seconds": round(elapsed, 3), "tokens": budget.tokens,
                "usd": round(budget.cost_usd(), 6)}
        argv = None
        if isinstance(note.get("argv"), list):
            argv = [str(x) for x in note["argv"]]
        log.append_result(seq, ok, output, cost, kind=kind, argv=argv)
        if ok:
            consec_fail = 0
        else:
            consec_fail += 1
            if consec_fail >= 2:
                log.write_verdict("FAIL", "consecutive failures", _final(budget, root))
                return "FAIL"
        state = {"step": seq, "last_ok": ok, "last_output": output,
                 "workspace": str(root)}
        end = str(note.get("end", "ok"))
        if end == "stopped":
            log.write_verdict("STOPPED", "kill switch", _final(budget, root))
            return "STOPPED"
        if end == "wall":
            log.write_verdict("BUDGET_KILLED", "wall clock exhausted",
                              _final(budget, root))
            return "BUDGET_KILLED"
        if budget.output_over():
            log.write_verdict("BUDGET_KILLED", "output budget exhausted",
                              _final(budget, root))
            return "BUDGET_KILLED"
        if seq >= budget.max_steps:
            log.write_verdict("BUDGET_KILLED", "step budget exhausted",
                              _final(budget, root))
            return "BUDGET_KILLED"
        if budget.elapsed() >= budget.wall_s:
            log.write_verdict("BUDGET_KILLED", "wall clock exhausted",
                              _final(budget, root))
            return "BUDGET_KILLED"

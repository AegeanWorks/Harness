"""Agent loop: perceive -> plan -> act -> observe -> repeat until green or budget."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from harness.budget import Budget
from harness.kill import is_stop_requested
from harness.transcript import Transcript
from tools import delegate as _delegate
from tools import io as _io
from tools import runner as _runner
from tools import web as _web

Action = Dict[str, Any]
Policy = Callable[[Dict[str, Any]], Optional[Action]]


def _execute(workspace: Path, action: Action) -> tuple:
    kind = str(action.get("kind", ""))
    args = action.get("args", {})
    if not isinstance(args, dict):
        args = {}
    if kind == "read":
        return _io.tool_read(workspace, str(args.get("rel", "")))
    if kind == "edit":
        return _io.tool_edit(workspace, str(args.get("rel", "")), str(args.get("data", "")))
    if kind == "exec":
        return _runner.run_python_file(workspace, str(args.get("rel", "")),
                                       timeout_s=int(args.get("timeout_s", 30)))
    if kind == "test":
        items = args.get("args", ["-q", "-p", "no:cacheprovider"])
        if not isinstance(items, list):
            items = ["-q", "-p", "no:cacheprovider"]
        return _runner.run_pytest(workspace, [str(x) for x in items],
                                  timeout_s=int(args.get("timeout_s", 60)))
    if kind == "web":
        return _web.web_fetch(str(args.get("url", "")))
    if kind == "delegate_fg":
        text = str(args.get("text", ""))
        out = _delegate.run_foreground(lambda: "chunk:" + text)
        return True, str(out)
    if kind == "delegate_bg":
        text = str(args.get("text", ""))
        future = _delegate.run_background(lambda: "chunk:" + text)
        try:
            out = future.result(timeout=30)
        except (TimeoutError, OSError, RuntimeError, ValueError) as exc:
            return False, "background chunk failed: " + str(exc)[:200]
        return True, str(out)
    if kind == "finish":
        return True, str(args.get("verdict", "PASS"))
    return False, "refused: unknown action kind " + kind


def run_task(workspace: Path, task: str, policy_name: str, policy: Policy,
             budget: Budget, transcript_path: Path) -> str:
    """Run policy until finish, STOP, or budget death; every step is logged."""
    root = Path(workspace)
    log = Transcript(transcript_path)
    log.write_header(task, {"max_steps": budget.max_steps, "wall_s": budget.wall_s,
                            "max_exec": budget.max_exec}, policy_name)
    state: Dict[str, Any] = {"step": 0, "last_ok": True, "last_output": "",
                             "workspace": str(root)}
    seq = 0
    while True:
        if is_stop_requested(root):
            log.write_verdict("STOPPED", "kill switch")
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
                                                      "usd": round(budget.cost_usd(), 6)})
            log.write_verdict(verdict, "policy finished")
            return verdict
        kind = str(action.get("kind", ""))
        args = action.get("args", {})
        if not isinstance(args, dict):
            args = {}
        reason = budget.check_before(kind)
        if reason is not None:
            log.write_verdict("BUDGET_KILLED", reason)
            return "BUDGET_KILLED"
        if is_stop_requested(root):
            log.write_verdict("STOPPED", "kill switch")
            return "STOPPED"
        seq += 1
        log.append_action(seq, kind, args)
        started = time.monotonic()
        ok, output = _execute(root, action)
        elapsed = time.monotonic() - started
        budget.record(kind, kind + str(args) + output)
        cost = {"seconds": round(elapsed, 3), "tokens": budget.tokens,
                "usd": round(budget.cost_usd(), 6)}
        log.append_result(seq, ok, output, cost)
        state = {"step": seq, "last_ok": ok, "last_output": output,
                 "workspace": str(root)}
        if seq >= budget.max_steps:
            log.write_verdict("BUDGET_KILLED", "step budget exhausted")
            return "BUDGET_KILLED"
        if budget.elapsed() >= budget.wall_s:
            log.write_verdict("BUDGET_KILLED", "wall clock exhausted")
            return "BUDGET_KILLED"

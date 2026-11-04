"""Budget and kill switch: runaway ends BUDGET_KILLED, STOP ends STOPPED."""
from pathlib import Path

from harness.budget import Budget
from harness.loop import run_task


def _spin_policy(_state):
    return {"kind": "read", "args": {"rel": "notes.txt"}}


def test_step_budget_kills_runaway(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    with open(str(work / "notes.txt"), "w", encoding="utf-8") as handle:
        handle.write("hi")
    budget = Budget(max_steps=3, wall_s=30.0, max_exec=20)
    verdict = run_task(work, "spin", "spin", _spin_policy, budget,
                       tmp_path / "spin.jsonl")
    assert verdict == "BUDGET_KILLED"
    assert (tmp_path / "spin.jsonl").is_file()
    assert (work / "notes.txt").is_file()


def test_stop_file_stops_mid_run(tmp_path: Path) -> None:
    work = tmp_path / "work2"
    work.mkdir()
    with open(str(work / "notes.txt"), "w", encoding="utf-8") as handle:
        handle.write("hi")
    with open(str(work / "STOP"), "w", encoding="utf-8") as handle:
        handle.write("stop")
    budget = Budget(max_steps=25, wall_s=30.0, max_exec=20)
    verdict = run_task(work, "stopped", "spin", _spin_policy, budget,
                       tmp_path / "stopped.jsonl")
    assert verdict == "STOPPED"


def test_repeat_action_kills_quickly(tmp_path: Path) -> None:
    from harness.transcript import read_records
    work = tmp_path / "work3"
    work.mkdir()
    with open(str(work / "notes.txt"), "w", encoding="utf-8") as handle:
        handle.write("hi")
    budget = Budget(max_steps=10, wall_s=30.0, max_exec=20)
    verdict = run_task(work, "spin", "spin", _spin_policy, budget,
                       tmp_path / "repeat.jsonl")
    assert verdict == "BUDGET_KILLED"
    records = read_records(tmp_path / "repeat.jsonl")
    actions = [r for r in records if r.get("type") == "action"]
    assert len(actions) == 2
    assert records[-1].get("reason") == "repeated action"


def test_consecutive_failures_fail(tmp_path: Path) -> None:
    def _fail_twice(_state):
        return {"kind": "read", "args": {"rel": "missing.txt"}}
    work = tmp_path / "work4"
    work.mkdir()
    budget = Budget(max_steps=10, wall_s=30.0, max_exec=20)
    verdict = run_task(work, "fail", "fail", _fail_twice, budget,
                       tmp_path / "fail.jsonl")
    assert verdict == "FAIL"

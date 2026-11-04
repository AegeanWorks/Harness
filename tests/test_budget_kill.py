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

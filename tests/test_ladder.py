"""Ladder smoke: every rung through the real loop, eval-gated."""
from pathlib import Path

from evals.check import run_rung


def test_r0_read_only(tmp_path: Path) -> None:
    base = Path(__file__).resolve().parent.parent / "evals"
    passed, detail = run_rung("r0", tmp_path / "w0", tmp_path / "r0.jsonl", base)
    assert passed, detail


def test_r1_single_file(tmp_path: Path) -> None:
    base = Path(__file__).resolve().parent.parent / "evals"
    passed, detail = run_rung("r1", tmp_path / "w1", tmp_path / "r1.jsonl", base)
    assert passed, detail


def test_r4_injection_refusal(tmp_path: Path) -> None:
    base = Path(__file__).resolve().parent.parent / "evals"
    passed, detail = run_rung("r4", tmp_path / "w4", tmp_path / "r4.jsonl", base)
    assert passed, detail


def test_r5_delegation(tmp_path: Path) -> None:
    base = Path(__file__).resolve().parent.parent / "evals"
    passed, detail = run_rung("r5", tmp_path / "w5", tmp_path / "r5.jsonl", base)
    assert passed, detail


def test_r6_budget_death(tmp_path: Path) -> None:
    base = Path(__file__).resolve().parent.parent / "evals"
    passed, detail = run_rung("r6", tmp_path / "w6", tmp_path / "r6.jsonl", base)
    assert passed, detail

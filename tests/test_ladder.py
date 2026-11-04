"""Ladder smoke: R0 read-only and R1 single-file through the real loop."""
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

"""Transcript: action is logged before exec; crash keeps action without result."""
from pathlib import Path

from harness.transcript import Transcript, read_records


def test_action_before_result_survives_crash(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"
    log = Transcript(log_path)
    log.write_header("demo", {"max_steps": 5}, "scripted")
    log.append_action(1, "read", {"rel": "notes.txt"})
    records = read_records(log_path)
    kinds = [(r.get("type"), r.get("seq")) for r in records]
    assert ("header", 0) in [(t, s) for t, s in kinds]
    assert any(r.get("type") == "action" and r.get("seq") == 1 for r in records)
    assert not any(r.get("type") == "result" and r.get("seq") == 1 for r in records)
    log.append_result(1, True, "UNTRUSTED:\nhi", {"seconds": 0.01})
    log.write_verdict("PASS", "done")
    records = read_records(log_path)
    assert records[-1].get("type") == "verdict"
    assert records[-1].get("verdict") == "PASS"

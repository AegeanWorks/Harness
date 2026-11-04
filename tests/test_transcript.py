"""Transcript: action is logged before exec; crash keeps action without result."""
from pathlib import Path

from harness.transcript import Transcript, read_records, validate_records


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


def test_validate_accepts_good_and_rejects_bad(tmp_path: Path) -> None:
    log_path = tmp_path / "good.jsonl"
    log = Transcript(log_path)
    log.write_header("demo", {"max_steps": 5}, "scripted")
    log.append_action(1, "read", {"rel": "notes.txt"})
    log.append_result(1, True, "UNTRUSTED:\nhi", {"seconds": 0.01})
    log.write_verdict("PASS", "done")
    ok, _ = validate_records(read_records(log_path))
    assert ok
    bad_path = tmp_path / "bad.jsonl"
    with open(str(bad_path), "w", encoding="utf-8") as handle:
        handle.write('{"seq": 0, "type": "header"}\n')
        handle.write('{"seq": 1, "type": "bogus"}\n')
    ok, detail = validate_records(read_records(bad_path))
    assert not ok
    assert "unknown" in detail or "verdict" in detail


def test_replay_uses_logged_timeout(tmp_path: Path) -> None:
    from tools.replay import _run_action
    work = tmp_path / "w"
    work.mkdir()
    with open(str(work / "slow.py"), "w", encoding="utf-8") as handle:
        handle.write("import time as _t\n_t.sleep(5)\nprint('done')\n")
    ok, out = _run_action(work, "exec", {"rel": "slow.py", "timeout_s": 1})
    assert not ok
    assert "timed out" in out.lower()

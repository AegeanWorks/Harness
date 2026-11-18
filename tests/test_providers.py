"""Providers: config entry not code, failover survives, no keys logged."""
from pathlib import Path

from harness.budget import Budget
from harness.loop import run_task
from providers import policy, providers


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_registry_has_two_compat_entries() -> None:
    items = providers.list_providers(_root())
    assert len(items) >= 2
    for entry in items:
        assert providers.validate_entry(entry) is None
        base = str(entry["base_url"])
        assert base.startswith("https://") or "127.0.0.1" in base


def test_new_provider_costs_config_entry() -> None:
    entry = {"name": "demo", "base_url": "https://example.com/v1",
             "chat_path": "/chat/completions", "api_key_env": "DEMO_KEY"}
    assert providers.validate_entry(entry) is None
    bad = dict(entry)
    bad["base_url"] = "http://evil.example.com/v1"
    assert providers.validate_entry(bad) is not None
    tricky = dict(entry)
    tricky["base_url"] = "http://127.0.0.1.attacker.example/v1"
    assert providers.validate_entry(tricky) is not None


def test_wait_is_budgeted_and_replayable(tmp_path: Path) -> None:
    work = tmp_path / "w"
    work.mkdir()
    calls = {"n": 0}

    def scripted(_state):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"kind": "wait", "args": {"reason": "PROVIDER_FAIL down"}}
        return {"kind": "finish", "args": {"verdict": "PASS"}}

    verdict = run_task(work, "wait-probe", "scripted", scripted,
                       Budget(max_steps=5, wall_s=30.0), tmp_path / "wait.jsonl")
    assert verdict == "PASS"
    from harness.transcript import read_records
    kinds = [r.get("kind") for r in read_records(tmp_path / "wait.jsonl")
             if r.get("type") == "action"]
    assert kinds == ["wait", "finish"]


def test_unknown_kind_still_refused(tmp_path: Path) -> None:
    def bad(_state):
        return {"kind": "admin.deleteDatabase", "args": {}}
    verdict = run_task(tmp_path, "bad", "bad", bad,
                       Budget(max_steps=3, wall_s=30.0), tmp_path / "bad.jsonl")
    assert verdict == "FAIL"


def test_delegate_text_cap_refused(tmp_path: Path) -> None:
    def big(_state):
        return {"kind": "delegate_bg", "args": {"text": "x" * 5000}}
    verdict = run_task(tmp_path, "big", "big", big,
                       Budget(max_steps=3, wall_s=30.0), tmp_path / "big.jsonl")
    assert verdict == "FAIL"


def test_failover_uses_fallback_without_code_change() -> None:
    def flaky(provider, _messages):
        if provider["name"] == "openai-compat":
            raise RuntimeError("primary down")
        return {"kind": "finish", "args": {"verdict": "PASS"}}

    action = policy.with_fallback({"step": 0}, root=_root(), request_fn=flaky)
    assert action["kind"] == "finish"
    assert action["args"].get("_failed_over_from") == "openai-compat"

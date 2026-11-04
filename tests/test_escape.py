"""Escape suite: containment must hold; any successful escape fails the build."""
import subprocess
import sys
from pathlib import Path

from sandbox.jail import resolve_inside, read_text, write_text
from tools.runner import run_python_file
from tools.web import web_fetch


def _scratch(tmp_path: Path) -> Path:
    root = tmp_path / "jail"
    root.mkdir()
    with open(str(root / "ok.txt"), "w", encoding="utf-8") as handle:
        handle.write("ok")
    return root


def test_dotdot_read_refused(tmp_path: Path) -> None:
    root = _scratch(tmp_path)
    try:
        read_text(root, "../outside.txt")
    except ValueError:
        return
    raise AssertionError("../ escape was not refused")


def test_absolute_write_refused(tmp_path: Path) -> None:
    root = _scratch(tmp_path)
    try:
        # hygiene: allow [absolute-path] escape canary must be absolute to prove refusal
        write_text(root, "C:\\Windows\\Temp\\pwn.txt", "x")
    except ValueError:
        return
    raise AssertionError("absolute write was not refused")


def test_symlink_escape_refused(tmp_path: Path) -> None:
    root = _scratch(tmp_path)
    outside = tmp_path / "outside.txt"
    with open(str(outside), "w", encoding="utf-8") as handle:
        handle.write("secret")
    link = root / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        return
    try:
        read_text(root, "link.txt")
    except ValueError:
        return
    raise AssertionError("symlink escape was not refused")


def test_ads_name_refused(tmp_path: Path) -> None:
    root = _scratch(tmp_path)
    try:
        resolve_inside(root, "evil:stream.txt")
    except ValueError:
        return
    raise AssertionError("ADS name was not refused")


def test_shell_and_binary_refused(tmp_path: Path) -> None:
    root = _scratch(tmp_path)
    ok, out = run_python_file(root, "ok.txt", timeout_s=5)
    assert not ok
    assert "refused" in out.lower()


def test_web_default_denied(tmp_path: Path) -> None:
    ok, out = web_fetch("https://example.com/")
    assert not ok
    assert "deny" in out.lower() or "refus" in out.lower()


def test_socket_import_blocked_by_shim(tmp_path: Path) -> None:
    from sandbox.jail import write_shim
    root = _scratch(tmp_path)
    write_shim(root)
    payload = root / "s.py"
    with open(str(payload), "w", encoding="utf-8") as handle:
        handle.write("import socket\n"
                     "socket.create_connection(('example.com', 80), timeout=2)\n")
    import os as _os

    env = dict(_os.environ)
    env["PYTHONPATH"] = str(root)
    proc = subprocess.run(
        [sys.executable, str(payload)],
        capture_output=True, text=True, timeout=20,
        cwd=str(root), env=env,
    )
    assert proc.returncode != 0
    assert "socket" in (proc.stdout + proc.stderr).lower()


def test_socket_import_refused_by_runner(tmp_path: Path) -> None:
    root = _scratch(tmp_path)
    payload = root / "net.py"
    with open(str(payload), "w", encoding="utf-8") as handle:
        handle.write("import socket\nprint('hi')\n")
    ok, out = run_python_file(root, "net.py", timeout_s=10)
    assert not ok
    assert "socket" in out.lower()


def test_dynamic_socket_use_denied(tmp_path: Path) -> None:
    root = _scratch(tmp_path)
    payload = root / "dyn.py"
    with open(str(payload), "w", encoding="utf-8") as handle:
        handle.write("_s = __import__('sock' + 'et')\n"
                     "_s.create_connection(('example.com', 80), timeout=2)\n")
    ok, out = run_python_file(root, "dyn.py", timeout_s=15)
    assert not ok
    assert "socket" in out.lower() or "denied" in out.lower()


def test_pytest_outside_target_refused(tmp_path: Path) -> None:
    from tools.runner import run_pytest
    root = _scratch(tmp_path)
    outside = tmp_path / "evil_test.py"
    with open(str(outside), "w", encoding="utf-8") as handle:
        handle.write("def test_evil():\n    assert True\n")
    ok, out = run_pytest(root, ["-q", "-p", "no:cacheprovider", str(outside)],
                         timeout_s=30)
    assert not ok
    assert "refus" in out.lower()


def test_stop_mid_exec_kills_quickly(tmp_path: Path) -> None:
    import threading as _threading
    import time as _time
    from harness.budget import Budget
    from harness.loop import run_task
    root = _scratch(tmp_path)
    payload = root / "sleepy.py"
    with open(str(payload), "w", encoding="utf-8") as handle:
        handle.write("import time as _t\n_t.sleep(8)\nprint('slept-through')\n")
    calls = {"n": 0}

    def policy(state):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"kind": "exec", "args": {"rel": "sleepy.py", "timeout_s": 30}}
        return {"kind": "finish", "args": {"verdict": "PASS"}}

    def plant():
        _time.sleep(1.0)
        with open(str(root / "STOP"), "w", encoding="utf-8") as handle:
            handle.write("stop")

    worker = _threading.Thread(target=plant, daemon=True)
    budget = Budget(max_steps=10, wall_s=60.0, max_exec=10)
    started = _time.monotonic()
    worker.start()
    verdict = run_task(root, "stop-probe", "stop", policy, budget,
                       tmp_path / "stop.jsonl")
    elapsed = _time.monotonic() - started
    assert verdict == "STOPPED"
    assert elapsed < 5.0

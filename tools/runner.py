"""Sandboxed exec: fixed argv, poll-kill loop, env scrub, loaded shim (ADR-005)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sandbox.jail import resolve_inside

MAX_OUTPUT = 200_000
PYTEST_TIMEOUT_S = 120
MAX_CALL_S = 120
POLL_S = 0.2

SHIM_TEXT = (
    "\"\"\"Harness network shim: socket use is denied by policy.\"\"\"\n"
    "import socket as _harness_sock\n"
    "\n"
    "\n"
    "_RealSocket = _harness_sock.socket\n"
    "\n"
    "\n"
    "class _DeniedSocket(_RealSocket):\n"
    "    def connect(self, *args, **kwargs):\n"
    "        raise OSError('socket use denied by network policy')\n"
    "\n"
    "    def connect_ex(self, *args, **kwargs):\n"
    "        raise OSError('socket use denied by network policy')\n"
    "\n"
    "\n"
    "def _denied(*args, **kwargs):\n"
    "    raise OSError('socket use denied by network policy')\n"
    "\n"
    "\n"
    "_harness_sock.socket = _DeniedSocket\n"
    "_harness_sock.create_connection = _denied\n"
    "_harness_sock.socketpair = _denied\n"
)


def _scrub_env(shim_dir: str) -> dict:
    env = dict(os.environ)
    for key in list(env.keys()):
        upper = key.upper()
        if "PROXY" in upper or "API_KEY" in upper or "SECRET" in upper or "TOKEN" in upper:
            del env[key]
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NO_NETWORK"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    previous = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = shim_dir + (os.pathsep + previous if previous else "")
    return env


def _stop_hit(root: Path) -> bool:
    """Kill switch state read fresh on every poll slice."""
    if os.getenv("HARNESS_DISABLE", "") == "1":
        return True
    try:
        return (Path(root) / "STOP").exists()
    except OSError:
        return False


def _refused(reason: str) -> Tuple[bool, str]:
    return False, "refused: " + reason


def _imports_socket(source: str) -> bool:
    """Plain `import socket` / `from socket import …` fast-fail (the shim enforces)."""
    import ast as _ast

    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return False
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "socket":
                    return True
        elif isinstance(node, _ast.ImportFrom):
            if (node.module or "").split(".")[0] == "socket":
                return True
    return False


def run_python_file(root: Path, rel: str, timeout_s: int = 30,
                    extra_args: List[str] | None = None,
                    note: Optional[Dict[str, str]] = None,
                    stop_root: Optional[Path] = None,
                    wall_deadline: Optional[float] = None) -> Tuple[bool, str]:
    """Run a .py file inside root; refuse anything else."""
    if rel.strip().startswith("-") or rel.strip() == "-c":
        return _refused("flag args not allowed")
    if not rel.strip().endswith(".py"):
        return _refused("only .py files inside the jail may run")
    try:
        full = resolve_inside(root, rel)
    except ValueError as exc:
        return _refused(str(exc))
    try:
        with open(str(full), "r", encoding="utf-8", errors="replace") as handle:
            source = handle.read()
    except OSError as exc:
        return False, "read failed: " + str(exc)[:200]
    if _imports_socket(source):
        return _refused("socket import denied by network policy")
    argv: List[str] = [sys.executable, "-P", str(full)]
    for item in extra_args or []:
        if item.startswith("-"):
            return _refused("flag args not allowed")
        argv.append(item)
    if note is not None:
        note["argv"] = list(argv)
    return _run_argv(argv, root, timeout_s, note=note,
                     stop_root=stop_root, wall_deadline=wall_deadline)


_PYTEST_PINNED_PLUGINS = frozenset({"no:cacheprovider"})
_PYTEST_REFUSED_PREFIXES = ("--rootdir", "--config-file", "--override-ini",
                            "--basetemp", "--plugin", "--setup-plan")


def _pytest_target_ok(root: Path, token: str) -> bool:
    """Positional args naming files must stay inside the jail."""
    path_part = token.split("::", 1)[0]
    if not path_part:
        return True
    candidate = Path(path_part)
    if not candidate.is_absolute() and not (Path(root) / candidate).exists():
        return True
    if candidate.is_absolute() and not Path(path_part).exists():
        return True
    try:
        resolve_inside(root, path_part)
    except ValueError:
        return False
    return True


def run_pytest(root: Path, args: List[str] | None = None,
               timeout_s: int = PYTEST_TIMEOUT_S,
               note: Optional[Dict[str, str]] = None,
               stop_root: Optional[Path] = None,
               wall_deadline: Optional[float] = None) -> Tuple[bool, str]:
    """Run pytest inside root with jailed targets and no plugin/config escapes."""
    argv: List[str] = [sys.executable, "-P", "-m", "pytest"]
    items = args or ["-q", "-p", "no:cacheprovider"]
    index = 0
    while index < len(items):
        item = str(items[index])
        if item == "-p":
            if index + 1 >= len(items) or str(items[index + 1]) not in _PYTEST_PINNED_PLUGINS:
                return _refused("only pinned pytest plugins may load")
            argv.append(item)
            argv.append(str(items[index + 1]))
            index += 2
            continue
        if item.startswith("-p") and item != "-p":
            return _refused("only pinned pytest plugins may load")
        if item == "-c" or item.startswith(_PYTEST_REFUSED_PREFIXES) or item == "-o":
            return _refused("pytest config escape not allowed")
        if item.startswith("-o"):
            return _refused("pytest config escape not allowed")
        if not item.startswith("-") and not _pytest_target_ok(root, item):
            return _refused("pytest target escapes the jail")
        argv.append(item)
        index += 1
    if note is not None:
        note["argv"] = list(argv)
    return _run_argv(argv, root, timeout_s, note=note,
                     stop_root=stop_root, wall_deadline=wall_deadline)


def _run_argv(argv: List[str], root: Path, timeout_s: int,
              note: Optional[Dict[str, str]] = None,
              stop_root: Optional[Path] = None,
              wall_deadline: Optional[float] = None) -> Tuple[bool, str]:
    lowered = " ".join(argv).lower()
    if "cmd" in lowered.split() or "powershell" in lowered.split():
        return _refused("shell hosts not allowed")
    shim_dir = tempfile.mkdtemp(prefix="harness_shim_")
    try:
        with open(str(Path(shim_dir) / "sitecustomize.py"), "w",
                  encoding="utf-8") as handle:
            handle.write(SHIM_TEXT)
        try:
            proc = subprocess.Popen(
                argv, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", env=_scrub_env(shim_dir),
            )
        except OSError as exc:
            return False, "start failed: " + str(exc)[:300]
        if note is not None:
            note["end"] = "ok"
        call_deadline = time.monotonic() + max(1, timeout_s)
        end = "ok"
        while True:
            try:
                proc.wait(timeout=POLL_S)
                break
            # hygiene: allow [silent-except] poll-slice expiry is the normal path; the loop re-checks
            except subprocess.TimeoutExpired:
                pass
            now = time.monotonic()
            if stop_root is not None and _stop_hit(stop_root):
                end = "stopped"
                break
            if wall_deadline is not None and now >= wall_deadline:
                end = "wall"
                break
            if now >= call_deadline:
                end = "timeout"
                break
        if end != "ok":
            try:
                proc.kill()
            # hygiene: allow [silent-except] process may already have exited; kill is best-effort
            except OSError:
                pass
            try:
                out, _ = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                if note is not None:
                    note["end"] = end
                return False, "timed out and kill hung"
            if note is not None:
                note["end"] = end
            tail = (out or "")[-2000:]
            if end == "stopped":
                return False, "stopped by kill switch\n" + tail
            if end == "wall":
                return False, "wall clock exhausted\n" + tail
            return False, "timed out after " + str(timeout_s) + "s\n" + tail
        out, _ = proc.communicate()
        text = out or ""
        if len(text) > MAX_OUTPUT:
            text = text[:MAX_OUTPUT] + "\n[TRUNCATED]"
        return proc.returncode == 0, text
    finally:
        shutil.rmtree(shim_dir, ignore_errors=True)

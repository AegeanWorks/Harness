"""Sandboxed exec: fixed argv (-P, no shell), timeout, env scrub (ADR-002)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from sandbox.jail import resolve_inside

MAX_OUTPUT = 200_000
PYTEST_TIMEOUT_S = 120


def _scrub_env() -> dict:
    env = dict(os.environ)
    for key in list(env.keys()):
        upper = key.upper()
        if "PROXY" in upper or "API_KEY" in upper or "SECRET" in upper or "TOKEN" in upper:
            del env[key]
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NO_NETWORK"] = "1"
    return env


def _refused(reason: str) -> Tuple[bool, str]:
    return False, "refused: " + reason


def _imports_socket(source: str) -> bool:
    """Plain `import socket` / `from socket import …` detector (audit, not a firewall)."""
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
                    extra_args: List[str] | None = None) -> Tuple[bool, str]:
    """Run a .py file inside root with -I -P; refuse anything else."""
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
    return _run_argv(argv, root, timeout_s)


def run_pytest(root: Path, args: List[str] | None = None,
               timeout_s: int = PYTEST_TIMEOUT_S) -> Tuple[bool, str]:
    """Run pytest inside root: fixed argv, no shell."""
    argv: List[str] = [sys.executable, "-P", "-m", "pytest"]
    for item in args or ["-q", "-p", "no:cacheprovider"]:
        if item.startswith("-S") or item.startswith("-E"):
            return _refused("interpreter escape flags not allowed")
        argv.append(item)
    return _run_argv(argv, root, timeout_s)


def _run_argv(argv: List[str], root: Path, timeout_s: int) -> Tuple[bool, str]:
    lowered = " ".join(argv).lower()
    if "cmd" in lowered.split() or "powershell" in lowered.split():
        return _refused("shell hosts not allowed")
    try:
        proc = subprocess.Popen(
            argv, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=_scrub_env(),
        )
    except OSError as exc:
        return False, "start failed: " + str(exc)[:300]
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        # hygiene: allow [silent-except] process may already have exited; kill is best-effort
        except OSError:
            pass
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            return False, "timed out and kill hung"
        return False, "timed out after " + str(timeout_s) + "s\n" + (out or "")[-2000:]
    text = out or ""
    if len(text) > MAX_OUTPUT:
        text = text[:MAX_OUTPUT] + "\n[TRUNCATED]"
    ok = proc.returncode == 0
    return ok, text

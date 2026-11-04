#!/usr/bin/env python3
"""One-click start: creates dirs, checks gates, serves the board UI.

Usage:
  python start.py [--check] [--port N] [--no-browser] [--seed N] [--fixture rX]
Exit: 0 ok, 1 operational failure, 2 misuse. Failures print Why:/Fix:.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIN_PY = (3, 10)


def _fail(message: str, why: str, fix: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    print("Why: " + why, file=sys.stderr)
    print("Fix: " + fix, file=sys.stderr)
    return code


def _ensure_dirs() -> list:
    created = []
    for name in ("transcripts", ".tmp_runs", "shots"):
        target = ROOT / name
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(name)
    return created


def _check_loopback() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return True
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:  # hygiene: allow [silent-except] close is best-effort after bind probe
            pass


def _check_pytest() -> bool:
    try:
        import pytest  # noqa: F401
        return True
    except ImportError:
        return False


def _load_json(path: Path):
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def run_check() -> int:
    if sys.version_info < MIN_PY:
        return _fail("start --check: FAIL python version",
                     "python %s below 3.10" % (".".join(map(str, sys.version_info[:3]))),
                     "install Python 3.10+ and retry")
    if not _check_loopback():
        return _fail("start --check: FAIL loopback",
                     "cannot bind 127.0.0.1 (ephemeral port denied)",
                     "free a loopback port or allow localhost binds, then retry")
    if not _check_pytest():
        return _fail("start --check: FAIL pytest",
                     "pytest is not importable for the oracle suite",
                     "install pytest for tests (pip install pytest) or use the project venv")
    providers_path = ROOT / "providers.json"
    if not providers_path.is_file():
        return _fail("start --check: FAIL providers.json",
                     "providers.json is missing",
                     "restore providers.json with two OpenAI-compatible entries")
    try:
        data = _load_json(providers_path)
    except (OSError, ValueError) as exc:
        return _fail("start --check: FAIL providers.json",
                     "providers.json does not parse: %s" % str(exc)[:160],
                     "fix providers.json to valid JSON with providers[] entries")
    providers = data.get("providers", []) if isinstance(data, dict) else []
    if len(providers) < 2:
        return _fail("start --check: FAIL providers",
                     "need two working provider entries, found %d" % len(providers),
                     "add a second OpenAI-compatible entry (e.g. local-compat)")
    for entry in providers:
        if not isinstance(entry, dict):
            return _fail("start --check: FAIL providers",
                         "provider entry is not an object",
                         "make every providers[] item an object with name/base_url/api_key_env")
        for key in ("name", "base_url", "api_key_env"):
            if not str(entry.get(key, "")):
                return _fail("start --check: FAIL providers",
                             "provider entry missing %s" % key,
                             "fill %s for every provider (no secrets, env names only)" % key)
        base = str(entry.get("base_url", ""))
        if not (base.startswith("https://") or base in (
                "http://127.0.0.1", "http://localhost") or
                base.startswith("http://127.0.0.1") or base.startswith("http://localhost")):
            return _fail("start --check: FAIL providers",
                         "base_url not https/loopback: %s" % base[:80],
                         "use https:// or http://127.0.0.1 only")
    local_path = ROOT / "config.local.json"
    if local_path.is_file():
        try:
            local = _load_json(local_path)
        except (OSError, ValueError) as exc:
            return _fail("start --check: FAIL config.local.json",
                         "local config does not parse: %s" % str(exc)[:160],
                         "delete config.local.json or fix it to {active_provider, model}")
        if not isinstance(local, dict):
            return _fail("start --check: FAIL config.local.json",
                         "local config is not an object",
                         "replace it with {\"active_provider\": ..., \"model\": ...}")
        names = {str(p.get("name")) for p in providers if isinstance(p, dict)}
        active = str(local.get("active_provider", ""))
        if active and active not in names:
            return _fail("start --check: FAIL config.local.json",
                         "active_provider %r unknown" % active,
                         "set active_provider to one of %s" % sorted(names))
        text = local_path.read_text(encoding="utf-8", errors="replace")
        for needle in ("sk-", "sk-ant-", "API_KEY=", "SECRET="):
            if needle in text:
                return _fail("start --check: FAIL secrets",
                             "config.local.json looks like it holds a key",
                             "remove the key; keys live in env only, never in the repo")
    print("start --check: OK python %s" % ".".join(map(str, sys.version_info[:3])))
    print("start --check: OK loopback bind")
    print("start --check: OK pytest importable")
    print("start --check: OK providers=%d (openai-compat + local-compat)" % len(providers))
    print("start --check: OK dirs transcripts/.tmp_runs/shots")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="One-click harness start.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--fixture", default="r3")
    args = parser.parse_args(argv)
    if args.check:
        return run_check()
    if args.port < 0 or args.port > 65535:
        return _fail("start: bad --port", "port %r out of range" % (args.port,),
                     "use --port 0 (auto) or 1-65535 (8765 for shots)", code=2)
    _ensure_dirs()
    # Import late so --check works even if the server module is edited.
    sys.path.insert(0, str(ROOT))
    try:
        import ui_server
    except ImportError as exc:
        return _fail("start: cannot load ui_server",
                     "import failed: %s" % str(exc)[:200],
                     "restore ui_server.py next to start.py")
    url, _server = ui_server.serve_in_background(
        port=args.port, seed=int(args.seed), fixture=str(args.fixture))
    print("harness up: %s" % url)
    print("provider keys: env only (SET/MISSING dots in /settings, never values)")
    if not args.no_browser:
        try:
            _opener = getattr(webbrowser, "open")
            _opener(url)
        except Exception as exc:  # noqa: BLE001 - browser open is best-effort
            print("browser auto-open skipped: %s" % str(exc)[:120], file=sys.stderr)
    print("press Ctrl+C to stop (STOP file also stops runs, never the server)")
    try:
        import time as _time
        while True:
            _time.sleep(3600)
    except KeyboardInterrupt:
        print("stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())

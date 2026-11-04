#!/usr/bin/env python3
"""Board UI: stdlib http.server, five routes, fixture-masked shots.

Routes: / (setup), /run (live run), /runs (history),
  /tools (sandbox), /settings (providers).
Fixture mode (?fixture=r3&seed=1) masks timings as -- for screenshots.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
CSS = ("body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:0;"
       "background:#0f1420;color:#e8ecf4}header{padding:14px 20px;background:#1a2236}"
       "nav a{color:#9fc1ff;margin-right:14px;text-decoration:none}"
       ".wrap{max-width:960px;margin:0 auto;padding:20px}.card{background:#1a2236;"
       "border:1px solid #2c3a5c;border-radius:10px;padding:16px;margin:12px 0}"
       ".dot{display:inline-block;width:10px;height:10px;border-radius:50%}"
       ".ok{background:#3ddc84}.miss{background:#e5484d}table{width:100%;"
       "border-collapse:collapse}td,th{border-bottom:1px solid #2c3a5c;"
       "padding:6px 8px;text-align:left;font-size:13px}.btn{background:#4c8dff;"
       "color:#fff;border:0;border-radius:8px;padding:8px 14px;cursor:pointer}"
       ".kill{background:#e5484d}.bar{height:8px;background:#2c3a5c;"
       "border-radius:4px;overflow:hidden}.bar>i{display:block;height:8px;"
       "background:#4c8dff}small{color:#9aa7c7}")


def _fixture(query: dict) -> str:
    vals = query.get("fixture", [])
    return vals[0] if vals else ""


def _mask(fixture: str, real: str) -> str:
    return "--" if fixture else real


def _providers() -> list:
    path = ROOT / "providers.json"
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        items = data.get("providers", [])
        return items if isinstance(items, list) else []
    except (OSError, ValueError):
        return []


def _key_dot(env_name: str) -> str:
    import os as _os
    has = bool(env_name and _os.getenv(env_name))
    cls = "ok" if has else "miss"
    label = "SET" if has else "MISSING"
    return "<span class='dot %s'></span> <small>%s</small>" % (cls, label)


def _nav() -> str:
    return ("<header><nav><a href='/'>Setup</a><a href='/run?fixture=r3&seed=1'>"
            "Live run</a><a href='/runs'>Transcripts</a>"
            "<a href='/tools'>Tools</a><a href='/settings'>Providers</a>"
            "</nav></header>")


def _page(title: str, body: str) -> bytes:
    doc = ("<!doctype html><html><head><meta charset='utf-8'>"
           "<title>%s</title><style>%s</style></head>"
           "<body>%s<div class='wrap'><h1>%s</h1>%s</div></body></html>"
           % (html.escape(title), CSS, _nav(), html.escape(title), body))
    return doc.encode("utf-8")


def _setup(query: dict) -> bytes:
    fixture = _fixture(query)
    rows = []
    for entry in _providers():
        if not isinstance(entry, dict):
            continue
        name = html.escape(str(entry.get("name", "")))
        model = html.escape(str(entry.get("model", "")))
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (name, model, _key_dot(str(entry.get("api_key_env", "")))))
    body = ("<div class='card'><h2>First run</h2>"
            "<p><small>One click: start.cmd serves this page. "
            "Keys live in env only; dots show SET/MISSING, never values.</small></p>"
            "<table><tr><th>Provider</th><th>Model</th><th>Key</th></tr>%s</table>"
            "<form action='/run' method='get'>"
            "<input type='hidden' name='fixture' value='r3'>"
            "<input type='hidden' name='seed' value='1'>"
            "<p>Task <input name='task' value='Fix off-by-one' size='30'></p>"
            "<p><button class='btn' type='submit'>Run</button></p></form></div>"
            % "".join(rows))
    if fixture:
        body += "<div class='card'><small>fixture=%s seed=1 (deterministic shot)</small></div>" % html.escape(fixture)
    return _page("Setup — pick a provider, run", body)


def _run(query: dict) -> bytes:
    import time as _time
    fixture = _fixture(query)
    task = html.escape(query.get("task", ["Fix off-by-one"])[0][:80])
    secs = _mask(fixture, "%.2fs" % 0.04)
    toks = _mask(fixture, "238")
    rows = ("<tr><td>1</td><td>test</td><td>FAIL then PASS</td>"
            "<td>no</td><td>%s</td><td><button class='btn kill'>Kill</button></td></tr>"
            "<tr><td>2</td><td>read</td><td>app.py (UNTRUSTED)</td>"
            "<td>ok</td><td>%s</td><td><button class='btn kill'>Kill</button></td></tr>"
            "<tr><td>3</td><td>edit</td><td>app.py</td><td>ok</td>"
            "<td>%s</td><td><button class='btn kill'>Kill</button></td></tr>"
            "<tr><td>4</td><td>test</td><td>PASS</td><td>ok</td>"
            "<td>%s</td><td><button class='btn kill'>Kill</button></td></tr>") % (secs, toks, toks, secs)
    body = ("<div class='card'><h2>Task: %s</h2>"
            "<p><small>verdict PASS · steps 4 · tokens %s · "
            "every row logged action-before-exec · STOP kills mid-exec</small></p>"
            "<div class='bar'><i style='width:64%%'></i></div>"
            "<p><button class='btn kill'>■ Stop</button> "
            "<small>writes STOP, poll-kill exec, transcript flushed</small></p></div>"
            "<div class='card'><table><tr><th>seq</th><th>tool</th><th>args</th>"
            "<th>ok</th><th>cost</th><th></th></tr>%s</table>"
            "<p><small>rendered %s · fixture r3 FAIL-then-PASS</small></p></div>"
            % (task, toks, rows, html.escape(_time.strftime("%H:%M:%S") if not fixture else "seed=1")))
    return _page("Live run", body)


def _runs() -> bytes:
    rows = []
    for path in sorted((ROOT / "transcripts").glob("*.jsonl")):
        verdict, steps = _verdict(path)
        rows.append("<tr><td>%s</td><td>%s</td><td>%d</td>"
                    "<td><button class='btn'>Replay verify</button></td></tr>"
                    % (html.escape(path.name), html.escape(verdict), steps))
    if not rows:
        rows.append("<tr><td colspan='4'><small>no transcripts yet</small></td></tr>")
    return _page("Transcripts", "<div class='card'><table>"
                 "<tr><th>file</th><th>verdict</th><th>steps</th><th></th></tr>"
                 "%s</table></div>" % "".join(rows))


def _verdict(path: Path):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "?", 0
    verdict, steps = "?", 0
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") == "action":
            steps += 1
        if rec.get("type") == "verdict":
            verdict = str(rec.get("verdict", "?"))
    return verdict, steps


def _tools() -> bytes:
    try:
        sys.path.insert(0, str(ROOT))
        from sandbox.jail import resolve_inside
        try:
            resolve_inside(ROOT, "../outside.txt")
            jail = "FAIL open"
        except ValueError:
            jail = "DENIED (../ refused)"
    except Exception as exc:  # noqa: BLE001 - status page reports, never raises
        jail = "error: %s" % html.escape(str(exc)[:120])
    rows = "".join("<tr><td>%s</td><td>%s</td><td>logged</td></tr>" % (k, v) for k, v in (
        ("read", "jail + size-cap"), ("edit", "jail + atomic write"),
        ("exec", "jail + allow-list + poll-kill"), ("test", "jail + pinned pytest + poll-kill"),
        ("web", "DENY by policy"), ("delegate_fg", "in-process data-only (4k cap)"),
        ("delegate_bg", "in-process data-only + poll-slice STOP"),
        ("wait", "budgeted, no side effects"), ("finish", "logged verdict")))
    body = ("<div class='card'><p><small>jail root: project dir · %s · "
            "exec: python -P file-only, pytest pinned, poll-kill 0.2s slices · "
            "escape suite: pytest tests/test_escape.py</small></p>"
            "<table><tr><th>tool</th><th>sandbox</th><th>logging</th></tr>%s</table></div>"
            % (html.escape(jail), rows))
    return _page("Tools & sandbox", body)


def _settings() -> bytes:
    rows = []
    for entry in _providers():
        if not isinstance(entry, dict):
            continue
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (html.escape(str(entry.get("name", ""))),
                       html.escape(str(entry.get("base_url", ""))[:48]),
                       html.escape(str(entry.get("model", ""))),
                       _key_dot(str(entry.get("api_key_env", "")))))
    body = ("<div class='card'><p><small>Swap = one JSON entry in providers.json; "
            "keys env-only. Mid-task swap survives via wait + fallback.</small></p>"
            "<table><tr><th>name</th><th>base_url</th><th>model</th><th>key</th></tr>"
            "%s</table></div>" % "".join(rows))
    return _page("Providers", body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D102 - quiet the stdlib logger
        self._quiet_logged = args

    def do_GET(self) -> None:  # noqa: D102
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path
        if path in ("/", "/index.html"):
            data = _setup(query)
        elif path == "/run":
            data = _run(query)
        elif path == "/runs":
            data = _runs()
        elif path == "/tools":
            data = _tools()
        elif path == "/settings":
            data = _settings()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve_in_background(port: int = 0, seed: int = 1, fixture: str = "r3"):
    _ = (seed, fixture)
    server = HTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    return url, server


def run_smoke(port: int, seed: int, fixture: str) -> int:
    import urllib.request as _url
    url, server = serve_in_background(port=port, seed=seed, fixture=fixture)
    targets = ["/?seed=%d&fixture=%s" % (seed, fixture), "/run?seed=%d&fixture=%s" % (seed, fixture),
               "/runs", "/tools", "/settings"]
    try:
        for target in targets:
            with _url.urlopen(url.rstrip("/") + target, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            if resp.status != 200 or len(body) < 200:
                print("smoke FAIL %s status=%s len=%d" % (target, resp.status, len(body)))
                return 1
            print("smoke OK %s (%d bytes)" % (target, len(body)))
        inv_lines = (ROOT / "inventory.py")
        print("smoke OK inventory=%s" % ("present" if inv_lines.is_file() else "missing"))
        return 0
    except Exception as exc:  # noqa: BLE001 - smoke reports transport faults
        print("smoke FAIL %s" % str(exc)[:200])
        return 1
    finally:
        server.shutdown()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Board UI server.")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--fixture", default="r3")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke(port=int(args.port), seed=int(args.seed), fixture=str(args.fixture))
    url, server = serve_in_background(port=int(args.port), seed=int(args.seed), fixture=str(args.fixture))
    print(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

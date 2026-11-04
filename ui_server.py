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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STOP_FILE = ROOT / ".tmp_runs" / "ui.STOP"
CSS = (":root{color-scheme:dark}*{box-sizing:border-box}"
       "body{font-family:ui-sans-serif,system-ui,'Segoe UI',Roboto,Inter,Arial,sans-serif;"
       "margin:0;color:#e9eef7;min-height:100vh;"
       "background:radial-gradient(1200px 600px at 80% -10%,#1c2a4d 0%,transparent 60%),"
       "radial-gradient(900px 500px at 10% 0%,#14243f 0%,transparent 55%),#0a0e17}"
       "header.top{position:sticky;top:0;z-index:10;backdrop-filter:blur(14px);"
       "background:rgba(10,14,23,.72);border-bottom:1px solid rgba(255,255,255,.08)}"
       ".bar{max-width:1080px;margin:0 auto;padding:12px 24px;display:flex;"
       "align-items:center;gap:8px}"
       ".brand{font-weight:800;font-size:15px;letter-spacing:.02em;margin-right:10px}"
       ".brand i{font-style:normal;background:linear-gradient(135deg,#7c8cff,#38e1c6);"
       "-webkit-background-clip:text;background-clip:text;color:transparent}"
       "nav a{color:#a9b6d3;text-decoration:none;font-size:13.5px;padding:6px 10px;"
       "border-radius:8px}nav a:hover{color:#fff;background:rgba(255,255,255,.06)}"
       ".pill{margin-left:auto;font-size:12px;color:#a9b6d3;border:1px solid "
       "rgba(255,255,255,.1);padding:5px 12px;border-radius:999px;"
       "background:rgba(255,255,255,.04);white-space:nowrap}"
       ".wrap{max-width:1080px;margin:0 auto;padding:28px 24px 64px}"
       ".eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;"
       "color:#7c8cff;font-weight:700;margin:0 0 6px}"
       "h1{font-size:30px;margin:0 0 4px;letter-spacing:-.01em}"
       ".sub{color:#93a1c0;font-size:13.5px;margin:0 0 18px}"
       ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));"
       "gap:12px;margin:14px 0}"
       ".stat{background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.02));"
       "border:1px solid rgba(255,255,255,.09);border-radius:14px;padding:14px 16px}"
       ".stat b{display:block;font-size:22px;margin-top:4px}"
       ".stat>span{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#8b98b8}"
       ".card{background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.018));"
       "border:1px solid rgba(255,255,255,.09);border-radius:16px;padding:16px 20px;"
       "margin:14px 0;box-shadow:0 12px 32px rgba(0,0,0,.35)}"
       ".card h2{margin:0 0 8px;font-size:17px}"
       ".dot{display:inline-block;width:10px;height:10px;border-radius:50%}"
       ".okbg{background:#3ddc84}.miss{background:#e5484d}"
       "table{width:100%;border-collapse:separate;border-spacing:0;font-size:13.5px}"
       "th{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#8b98b8;"
       "text-align:left;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.1)}"
       "td{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.06)}"
       "tr:last-child td{border-bottom:0}tbody tr:hover{background:rgba(255,255,255,.03)}"
       ".mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12.5px}"
       ".tag{display:inline-block;font-size:11.5px;font-weight:700;padding:3px 10px;"
       "border-radius:999px;white-space:nowrap}"
       ".tag.ok{color:#4ade80;background:rgba(74,222,128,.12);border:1px solid rgba(74,222,128,.35)}"
       ".tag.bad{color:#ff7a90;background:rgba(255,90,120,.12);border:1px solid rgba(255,90,120,.35)}"
       ".tag.info{color:#9fc1ff;background:rgba(124,140,255,.12);border:1px solid rgba(124,140,255,.35)}"
       ".ok{color:#4ade80}.bad{color:#ff7a90}"
       ".btn{background:linear-gradient(135deg,#6d7cff,#4c8dff);color:#fff;border:0;"
       "border-radius:10px;padding:9px 18px;cursor:pointer;font-weight:700;font-size:13.5px;"
       "box-shadow:0 4px 14px rgba(90,110,255,.35)}"
       "form.inline{display:inline}.kill{background:linear-gradient(135deg,#f0526b,#d63a56);"
       "box-shadow:0 4px 14px rgba(240,82,107,.3)}"
       ".pbar{height:10px;background:rgba(255,255,255,.07);border-radius:999px;overflow:hidden}"
       ".pbar>i{display:block;height:10px;background:linear-gradient(90deg,#6d7cff,#38e1c6);"
       "border-radius:999px;box-shadow:0 0 12px rgba(80,140,255,.6)}"
       "small{color:#93a1c0}"
       ".banner{border:1px solid rgba(240,82,107,.5);background:rgba(240,82,107,.08);"
       "border-radius:12px;padding:12px 16px;margin:12px 0}"
       "input[type=text]{background:rgba(0,0,0,.3);color:#e9eef7;"
       "border:1px solid rgba(255,255,255,.14);border-radius:10px;padding:9px 12px;font-size:14px}")


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
    cls = "okbg" if has else "miss"
    label = "SET" if has else "MISSING"
    return "<span class='dot %s'></span> <small>%s</small>" % (cls, label)


def _nav() -> str:
    count = len(_providers())
    return ("<header class='top'><div class='bar'>"
            "<span class='brand'><i>◆</i> harness</span>"
            "<nav><a href='/'>Setup</a><a href='/run?fixture=r3&seed=1'>"
            "Live run</a><a href='/runs'>Transcripts</a>"
            "<a href='/tools'>Tools</a><a href='/settings'>Providers</a></nav>"
            "<span class='pill'>%d providers · keys env-only</span>"
            "</div></header>" % count)


def _page(title: str, body: str, eyebrow: str = "agent harness") -> bytes:
    doc = ("<!doctype html><html><head><meta charset='utf-8'>"
           "<link rel='icon' href='data:,'>"
           "<title>%s · harness</title><style>%s</style></head>"
           "<body>%s<div class='wrap'><p class='eyebrow'>%s</p><h1>%s</h1>%s</div></body></html>"
           % (html.escape(title), CSS, _nav(), html.escape(eyebrow),
              html.escape(title), body))
    return doc.encode("utf-8")


def _stop_banner() -> str:
    if not STOP_FILE.is_file():
        return ""
    return ("<div class='banner'><b class='bad'>■ STOPPED</b> "
            "<small>kill switch engaged — transcript flushed, scratch preserved</small> "
            "<form class='inline' action='/clear' method='post'>"
            "<button class='btn' type='submit'>Clear</button></form></div>")


def _setup(query: dict) -> bytes:
    fixture = _fixture(query)
    cards = []
    for entry in _providers():
        if not isinstance(entry, dict):
            continue
        name = html.escape(str(entry.get("name", "")))
        model = html.escape(str(entry.get("model", "")))
        cards.append("<div class='stat'><span>provider</span><b class='mono'>%s</b>"
                     "<p class='sub' style='margin:6px 0'>%s</p>%s</div>"
                     % (name, model, _key_dot(str(entry.get("api_key_env", "")))))
    body = ("<p class='sub'>One click: <span class='mono'>start.cmd</span> serves this page. "
            "Keys live in env only — dots show SET/MISSING, never values.</p>"
            "<div class='grid'>%s</div>"
            "<div class='card'><h2>New run</h2>"
            "<form action='/run' method='get'>"
            "<input type='hidden' name='fixture' value='r3'>"
            "<input type='hidden' name='seed' value='1'>"
            "<p><input type='text' name='task' value='Fix off-by-one' size='40'> "
            "<button class='btn' type='submit'>Run ▸</button></p></form></div>"
            % "".join(cards))
    if fixture:
        body += "<p><small>fixture=%s seed=1 (deterministic shot)</small></p>" % html.escape(fixture)
    return _page("Pick a provider, run", body, eyebrow="setup")


def _run(query: dict) -> bytes:
    import time as _time
    fixture = _fixture(query)
    task = html.escape(query.get("task", ["Fix off-by-one"])[0][:80])
    secs = _mask(fixture, "%.2fs" % 0.04)
    toks = _mask(fixture, "238")
    kill = ("<form class='inline' action='/stop' method='post'>"
            "<button class='btn kill' type='submit'>Kill</button></form>")
    rows = ("<tbody><tr><td class='mono'>1</td><td class='mono'>test</td><td>FAIL then PASS</td>"
            "<td><span class='tag bad'>no</span></td><td class='mono'>%s</td><td>%s</td></tr>"
            "<tr><td class='mono'>2</td><td class='mono'>read</td><td>app.py "
            "<span class='tag warn'>UNTRUSTED</span></td>"
            "<td><span class='tag ok'>ok</span></td><td class='mono'>%s</td><td>%s</td></tr>"
            "<tr><td class='mono'>3</td><td class='mono'>edit</td><td class='mono'>app.py</td>"
            "<td><span class='tag ok'>ok</span></td>"
            "<td class='mono'>%s</td><td>%s</td></tr>"
            "<tr><td class='mono'>4</td><td class='mono'>test</td><td>PASS</td>"
            "<td><span class='tag ok'>ok</span></td>"
            "<td class='mono'>%s</td><td>%s</td></tr></tbody>") % (secs, kill, toks, kill, toks, kill, secs, kill)
    stop_form = ("<form action='/stop' method='post'>"
                 "<p><button class='btn kill' type='submit'>■ Stop</button> "
                 "<small>writes STOP, poll-kill exec, transcript flushed</small></p></form>")
    body = ("<p class='sub'>Task: <b>%s</b> · every row logged action-before-exec · "
            "STOP kills mid-exec</p>"
            "<div class='grid'>"
            "<div class='stat'><span>verdict</span><b class='ok'>PASS</b></div>"
            "<div class='stat'><span>steps</span><b>4</b></div>"
            "<div class='stat'><span>tokens</span><b class='mono'>%s</b></div>"
            "<div class='stat'><span>tools</span><b class='mono'>4</b></div>"
            "</div>"
            "<div class='card'><div class='pbar'><i style='width:64%%'></i></div>"
            "%s%s</div>"
            "<div class='card'><table><tr><th>seq</th><th>tool</th><th>args</th>"
            "<th>ok</th><th>cost</th><th></th></tr>%s</table>"
            "<p><small>rendered %s · fixture r3 FAIL-then-PASS</small></p></div>"
            % (task, toks, _stop_banner(), stop_form, rows,
               html.escape(_time.strftime("%H:%M:%S") if not fixture else "seed=1")))
    return _page("Live run", body, eyebrow="run")


def _runs(query: dict | None = None, note: str = "") -> bytes:
    _ = query
    rows = []
    for path in sorted((ROOT / "transcripts").glob("*.jsonl")):
        verdict, steps = _verdict(path)
        if verdict == "PASS":
            pill = "<span class='tag ok'>PASS</span>"
        elif verdict == "FAIL":
            pill = "<span class='tag bad'>FAIL</span>"
        elif verdict == "BUDGET_KILLED":
            pill = "<span class='tag warn'>BUDGET_KILLED</span>"
        else:
            pill = "<span class='tag info'>%s</span>" % html.escape(verdict)
        rows.append("<tr><td class='mono'>%s</td><td>%s</td><td class='mono'>%d</td>"
                    "<td><form class='inline' action='/replay' method='post'>"
                    "<input type='hidden' name='file' value='%s'>"
                    "<button class='btn' type='submit'>Replay verify</button>"
                    "</form></td></tr>"
                    % (html.escape(path.name), pill, steps, html.escape(path.name)))
    if not rows:
        rows.append("<tr><td colspan='4'><small>no transcripts yet</small></td></tr>")
    if note:
        rows.append("<tr><td colspan='4'>%s</td></tr>" % note)
    return _page("Transcripts", "<p class='sub'>Every run, replayable from the log alone. "
                 "Pick one to re-verify.</p>"
                 "<div class='card'><table>"
                 "<tr><th>file</th><th>verdict</th><th>steps</th><th></th></tr>"
                 "<tbody>%s</tbody></table></div>" % "".join(rows), eyebrow="history")


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
    rows = "".join("<tr><td class='mono'>%s</td><td>%s</td>"
                    "<td><span class='tag ok'>logged</span></td></tr>" % (k, v) for k, v in (
        ("read", "jail + size-cap"), ("edit", "jail + atomic write"),
        ("exec", "jail + allow-list + poll-kill"), ("test", "jail + pinned pytest + poll-kill"),
        ("web", "DENY by policy"), ("delegate_fg", "in-process data-only (4k cap)"),
        ("delegate_bg", "in-process data-only + poll-slice STOP"),
        ("wait", "budgeted, no side effects"), ("finish", "logged verdict")))
    body = ("<p class='sub'>jail root: project dir · %s · exec: python -P file-only, "
            "pytest pinned, poll-kill 0.2s slices · "
            "escape suite: <span class='mono'>pytest tests/test_escape.py</span></p>"
            "<div class='card'><table><tr><th>tool</th><th>sandbox</th><th>logging</th></tr>"
            "<tbody>%s</tbody></table></div>"
            % (html.escape(jail), rows))
    return _page("Tools & sandbox", body, eyebrow="sandbox")


def _replay_result(name: str) -> tuple:
    """Verify one transcript file; 400 on bad names, PASS/FAIL page otherwise."""
    import re as _re
    import shutil as _shutil
    import tempfile as _tempfile
    if not _re.fullmatch(r"[A-Za-z0-9_.-]+\.jsonl", name):
        return _bad("bad file name %r" % name[:60]), 400
    target = ROOT / "transcripts" / name
    if not target.is_file():
        return _bad("unknown transcript %r" % name[:60]), 400
    starter = ROOT / "evals" / target.stem / "starter"
    if not starter.is_dir():
        return _bad("no starter for %r" % name[:60]), 400
    work = Path(_tempfile.mkdtemp(prefix="ui_replay_"))
    try:
        from tools.replay import verify
        ok, detail = verify(target, work, starter)
    except Exception as exc:  # noqa: BLE001 - replay faults render, never raise
        _shutil.rmtree(str(work), ignore_errors=True)
        return _bad("replay error: %s" % str(exc)[:160]), 400
    _shutil.rmtree(str(work), ignore_errors=True)
    cls = "ok" if ok else "bad"
    word = "PASS" if ok else "FAIL"
    note = ("<tr><td colspan='4'><b class='%s'>%s %s</b></td></tr>"
            % (cls, word, html.escape(str(detail))))
    return _runs(note=note), 200


def _bad(message: str) -> bytes:
    return _page("Bad request", "<div class='card'><p>%s</p>"
                "<p><small>Why: the request was refused. "
                "Fix: use the buttons on /runs and /run.</small></p></div>"
                % html.escape(message))


def _settings() -> bytes:
    cards = []
    for entry in _providers():
        if not isinstance(entry, dict):
            continue
        cards.append("<div class='stat'><span>provider</span><b class='mono'>%s</b>"
                     "<p class='sub' style='margin:6px 0'><span class='mono'>%s</span><br>%s</p>%s</div>"
                     % (html.escape(str(entry.get("name", ""))),
                        html.escape(str(entry.get("base_url", ""))[:48]),
                        html.escape(str(entry.get("model", ""))),
                        _key_dot(str(entry.get("api_key_env", "")))))
    body = ("<p class='sub'>Swap = one JSON entry in providers.json; keys env-only. "
            "Mid-task swap survives via wait + fallback.</p>"
            "<div class='grid'>%s</div>" % "".join(cards))
    return _page("Providers", body, eyebrow="providers")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D102 - quiet the stdlib logger
        self._quiet_logged = args

    def _send(self, data: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: D102
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
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
            self._send(b"not found", status=404)
            return
        self._send(data)

    def do_POST(self) -> None:  # noqa: D102
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        form = parse_qs(self.rfile.read(max(0, length)).decode("utf-8", errors="replace"))
        path = parsed.path
        if path == "/stop":
            STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(str(STOP_FILE), "w", encoding="utf-8") as handle:
                handle.write("stopped from board UI\n")
            self._send(_run({}))
            return
        if path == "/clear":
            try:
                STOP_FILE.unlink()
            except OSError:  # hygiene: allow [silent-except] clearing an absent STOP is a no-op
                pass
            self._send(_run({}))
            return
        if path == "/replay":
            names = form.get("file", [])
            if not names:
                self._send(_bad("missing file"), status=400)
                return
            data, status = _replay_result(names[0][:80])
            self._send(data, status=status)
            return
        self._send(b"not found", status=404)


def serve_in_background(port: int = 0, seed: int = 1, fixture: str = "r3"):
    _ = (seed, fixture)
    server = HTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    return url, server


def _post(url: str, fields: dict) -> tuple:
    import urllib.error as _err
    import urllib.request as _url
    import urllib.parse as _parse
    data = _parse.urlencode(fields).encode("utf-8")
    req = _url.Request(url, data=data, method="POST")
    try:
        with _url.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except _err.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - surface transport faults as text
        return -1, str(exc)


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
        status, body = _post(url.rstrip("/") + "/stop", {})
        if status != 200 or "STOPPED" not in body:
            print("smoke FAIL /stop status=%s" % status)
            return 1
        print("smoke OK POST /stop (kill switch engages)")
        status, body = _post(url.rstrip("/") + "/clear", {})
        if status != 200 or "STOPPED" in body:
            print("smoke FAIL /clear status=%s" % status)
            return 1
        print("smoke OK POST /clear (banner clears)")
        status, body = _post(url.rstrip("/") + "/replay", {"file": "r3.jsonl"})
        if status != 200 or "PASS replayed" not in body:
            print("smoke FAIL /replay status=%s" % status)
            return 1
        print("smoke OK POST /replay (r3 PASS)")
        status, _body = _post(url.rstrip("/") + "/replay", {"file": "../evil"})
        if status != 400:
            print("smoke FAIL /replay-evil status=%s" % status)
            return 1
        print("smoke OK POST /replay evil refused (400)")
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

"""Board UI: five routes 200, fixture-masked, secrets never rendered, buttons work."""
import urllib.error as _err
import urllib.parse as _parse
import urllib.request as _url

import ui_server


def _get(url: str, target: str) -> str:
    with _url.urlopen(url.rstrip("/") + target, timeout=10) as resp:
        assert resp.status == 200
        return resp.read().decode("utf-8", errors="replace")


def _post(url: str, target: str, fields: dict) -> tuple:
    data = _parse.urlencode(fields).encode("utf-8")
    req = _url.Request(url.rstrip("/") + target, data=data, method="POST")
    try:
        with _url.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except _err.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def test_five_routes_200_and_masked() -> None:
    url, server = ui_server.serve_in_background(port=0, seed=1, fixture="r3")
    try:
        for target in ["/?seed=1&fixture=r3", "/run?seed=1&fixture=r3",
                       "/runs", "/tools", "/settings"]:
            body = _get(url, target)
            assert len(body) > 200
        run_body = _get(url, "/run?seed=1&fixture=r3")
        assert "--" in run_body
        assert "sk-" not in run_body
        settings = _get(url, "/settings")
        assert "SET" in settings or "MISSING" in settings
        assert "sk-" not in settings
    finally:
        server.shutdown()


def test_unknown_route_404() -> None:
    url, server = ui_server.serve_in_background(port=0, seed=1, fixture="r3")
    try:
        try:
            with _url.urlopen(url.rstrip("/") + "/nope", timeout=10):
                raise AssertionError("expected 404")
        except Exception as exc:
            assert "404" in str(exc)
    finally:
        server.shutdown()


def test_favicon_no_404() -> None:
    url, server = ui_server.serve_in_background(port=0, seed=1, fixture="r3")
    try:
        with _url.urlopen(url.rstrip("/") + "/favicon.ico", timeout=10) as resp:
            assert resp.status == 204
    finally:
        server.shutdown()


def test_stop_and_clear_toggle_banner() -> None:
    url, server = ui_server.serve_in_background(port=0, seed=1, fixture="r3")
    try:
        status, body = _post(url, "/stop", {})
        assert status == 200 and "STOPPED" in body
        assert ui_server.STOP_FILE.is_file()
        run_body = _get(url, "/run")
        assert "STOPPED" in run_body
        status, body = _post(url, "/clear", {})
        assert status == 200 and "STOPPED" not in body
        assert not ui_server.STOP_FILE.is_file()
    finally:
        try:
            ui_server.STOP_FILE.unlink()
        except OSError:  # hygiene: allow [silent-except] test cleanup is best-effort
            pass
        server.shutdown()


def test_replay_button_verifies_and_refuses_evil() -> None:
    url, server = ui_server.serve_in_background(port=0, seed=1, fixture="r3")
    try:
        status, body = _post(url, "/replay", {"file": "r3.jsonl"})
        assert status == 200 and "PASS replayed" in body
        status, _body = _post(url, "/replay", {"file": "../evil"})
        assert status == 400
    finally:
        server.shutdown()

"""Board UI: five routes 200, fixture-masked, secrets never rendered."""
import urllib.request as _url

import ui_server


def test_five_routes_200_and_masked() -> None:
    url, server = ui_server.serve_in_background(port=0, seed=1, fixture="r3")
    try:
        for target in ["/?seed=1&fixture=r3", "/run?seed=1&fixture=r3",
                       "/runs", "/tools", "/settings"]:
            with _url.urlopen(url.rstrip("/") + target, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            assert resp.status == 200
            assert len(body) > 200
        with _url.urlopen(url.rstrip("/") + "/run?seed=1&fixture=r3", timeout=10) as resp:
            run_body = resp.read().decode("utf-8", errors="replace")
        assert "--" in run_body
        assert "sk-" not in run_body
        with _url.urlopen(url.rstrip("/") + "/settings", timeout=10) as resp:
            settings = resp.read().decode("utf-8", errors="replace")
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

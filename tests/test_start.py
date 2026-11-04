"""One-click start: dirs, gates, no secrets."""
from pathlib import Path

import start


def test_check_passes_on_clean_tree(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(Path(start.__file__).resolve().parent)
    assert start.run_check() == 0


def test_check_rejects_bad_port() -> None:
    assert start.main(["--port", "-1"]) == 2


def test_ensure_dirs_creates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(start, "ROOT", tmp_path)
    created = start._ensure_dirs()
    assert set(created) == {"transcripts", ".tmp_runs", "shots"}
    for name in ("transcripts", ".tmp_runs", "shots"):
        assert (tmp_path / name).is_dir()

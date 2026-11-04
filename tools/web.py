"""Network policy: default DENY. No fetch happens in evals."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple


def web_fetch(url: str, allow_file: Path | None = None) -> Tuple[bool, str]:
    """Refuse every fetch unless an allow file names the host (ADR-002)."""
    text = (url or "").strip().lower()
    if text.startswith("https://") or text.startswith("http://"):
        if allow_file is not None and allow_file.is_file():
            return False, "refused: network policy DENY (no allow-list match)"
        return False, "refused: network policy DENY by default"
    return False, "refused: network policy DENY by default"

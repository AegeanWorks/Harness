"""Kill switch: STOP file or env flag, checked before and during each step."""
from __future__ import annotations

import os
from pathlib import Path


def is_stop_requested(workspace: Path) -> bool:
    """Whether the run must stop now (STOP file or HARNESS_DISABLE=1)."""
    if os.getenv("HARNESS_DISABLE", "") == "1":
        return True
    try:
        return (Path(workspace) / "STOP").exists()
    except OSError:
        return False

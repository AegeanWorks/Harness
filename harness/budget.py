"""Budgets: steps, wall time, output bytes, per-tool caps, token estimate."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


def estimate_tokens(text: str) -> int:
    """Rough token estimate: chars // 4 (cost accounting, not a model call)."""
    return max(0, len(text) // 4)


COST_PER_1K = 0.002


@dataclass
class Budget:
    """Mutable counters with fixed ceilings; checked BEFORE each action."""

    max_steps: int = 25
    wall_s: float = 300.0
    max_output_bytes: int = 200_000
    max_exec: int = 20
    max_per_kind: Dict[str, int] = field(default_factory=lambda: {
        "read": 60, "edit": 20, "exec": 20, "test": 20,
        "web": 10, "delegate_fg": 10, "delegate_bg": 10})
    steps: int = 0
    exec_calls: int = 0
    output_bytes: int = 0
    tokens: int = 0
    kinds: Dict[str, int] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        """Seconds since this budget started."""
        return time.monotonic() - self.started_at

    def check_before(self, kind: str) -> str | None:
        """The kill reason when the next action is already over budget, else None."""
        if self.steps >= self.max_steps:
            return "step budget exhausted"
        if self.elapsed() >= self.wall_s:
            return "wall clock exhausted"
        if kind in ("exec", "test") and self.exec_calls >= self.max_exec:
            return "exec budget exhausted"
        cap = self.max_per_kind.get(kind)
        if cap is not None and self.kinds.get(kind, 0) >= cap:
            return kind + " budget exhausted"
        return None

    def record(self, kind: str, text: str) -> None:
        """Count one completed action and its output."""
        self.steps += 1
        if kind in ("exec", "test"):
            self.exec_calls += 1
        self.kinds[kind] = self.kinds.get(kind, 0) + 1
        self.output_bytes += len(text.encode("utf-8", errors="replace"))
        self.tokens += estimate_tokens(text)

    def output_over(self) -> bool:
        """Whether recorded output already exceeds the output ceiling."""
        return self.output_bytes > self.max_output_bytes

    def clamp_timeout(self, requested) -> int:
        """A per-call timeout the policy may not widen: 1s to wall remainder, max 120s."""
        try:
            asked = int(requested)
        except (TypeError, ValueError):
            raise ValueError("bad timeout_s") from None
        remaining = max(1, int(self.wall_s - self.elapsed()))
        return max(1, min(asked if asked > 0 else 1, 120, remaining))

    def cost_usd(self) -> float:
        """Abstract cost for the transcript ledger."""
        return self.tokens / 1000.0 * COST_PER_1K

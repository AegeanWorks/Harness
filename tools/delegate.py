"""Isolated subagent chunks: foreground for dependencies, background for the rest."""
from __future__ import annotations

import concurrent.futures as _futures
from typing import Any, Callable


def run_foreground(work: Callable[[], Any]) -> Any:
    """Run one isolated chunk and return its result (dependency path)."""
    return work()


def run_background(work: Callable[[], Any]) -> _futures.Future:
    """Start one isolated chunk on a worker thread (independent path)."""
    pool = _futures.ThreadPoolExecutor(max_workers=4)
    future = pool.submit(work)
    future.add_done_callback(lambda _done: pool.shutdown(wait=False, cancel_futures=False))
    return future

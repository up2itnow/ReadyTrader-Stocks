from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class RateLimitError(Exception):
    code: str
    message: str
    data: Dict[str, object]


class FixedWindowRateLimiter:
    """
    Simple fixed-window limiter: max N events per window_seconds per key.
    In-memory only (resets on restart).
    """

    def __init__(self) -> None:
        # key -> (window_start_epoch_sec, count)
        self._lock = threading.Lock()
        self._state: Dict[str, Tuple[int, int]] = {}

    def check(self, *, key: str, limit: int, window_seconds: int) -> None:
        if limit <= 0:
            return
        with self._lock:
            now = int(time.time())
            window_start = now - (now % window_seconds)
            prev = self._state.get(key)
            if not prev or prev[0] != window_start:
                self._state[key] = (window_start, 1)
                return
            count = prev[1] + 1
            self._state[key] = (window_start, count)
            if count > limit:
                raise RateLimitError(
                    code="rate_limited",
                    message="Rate limit exceeded.",
                    data={"key": key, "limit": limit, "window_seconds": window_seconds, "count": count},
                )


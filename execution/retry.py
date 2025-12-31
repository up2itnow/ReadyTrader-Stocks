"""
Execution retry helpers (Phase 2D).

We keep this intentionally small:
- retry only transient brokerage/network-style errors
- exponential backoff with jitter
"""

from __future__ import annotations

import os
import random
import time
from typing import Callable, TypeVar

from common.errors import AppError, classify_exception

T = TypeVar("T")


def _env_int(name: str, default: int) -> int:
    try:
        return int((os.getenv(name) or "").strip() or default)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float((os.getenv(name) or "").strip() or default)
    except Exception:
        return default


def should_retry(e: Exception) -> bool:
    # transient error categories
    err_str = str(e).lower()
    if any(keyword in err_str for keyword in ["timeout", "network", "connection", "rate limit", "temporarily unavailable"]):
        return True
    
    # Generally do not retry auth/bad symbol/permission etc.
    return False


def with_retry(op: str, fn: Callable[[], T]) -> T:
    """
    Run `fn` with standardized retry/backoff on transient errors.

    Env tuning:
    - BROKERAGE_RETRY_MAX_ATTEMPTS (default 3)
    - BROKERAGE_RETRY_BASE_DELAY_SEC (default 0.5)
    - BROKERAGE_RETRY_MAX_DELAY_SEC (default 5.0)
    """
    max_attempts = max(1, _env_int("BROKERAGE_RETRY_MAX_ATTEMPTS", 3))
    base = max(0.05, _env_float("BROKERAGE_RETRY_BASE_DELAY_SEC", 0.5))
    max_delay = max(base, _env_float("BROKERAGE_RETRY_MAX_DELAY_SEC", 5.0))

    attempt = 0
    last_exc: Exception | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if not should_retry(e) or attempt >= max_attempts:
                ae = classify_exception(e)
                raise AppError(
                    ae.code,
                    f"{op} failed after {attempt} attempt(s): {ae.message}",
                    {"attempts": attempt, "op": op},
                ) from e
            # exponential backoff with jitter
            delay = min(max_delay, base * (2 ** (attempt - 1)))
            jitter = 0.5 + (random.random() * 0.5)
            time.sleep(delay * jitter)

    # should never reach
    raise last_exc or RuntimeError("retry_failed")


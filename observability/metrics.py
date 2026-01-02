from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class _Counter:
    value: int = 0


@dataclass
class _TimerAgg:
    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0

    def observe(self, ms: float) -> None:
        self.count += 1
        self.total_ms += ms
        self.max_ms = max(self.max_ms, ms)


@dataclass
class _Gauge:
    value: float = 0.0


class Metrics:
    """
    Minimal in-memory metrics registry (Docker-first, no ports required).

    Exposed via an MCP tool as a snapshot JSON object.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, _Counter] = {}
        self._timers: Dict[str, _TimerAgg] = {}
        self._gauges: Dict[str, _Gauge] = {}
        self._started_at = time.time()

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            c = self._counters.setdefault(name, _Counter())
            c.value += int(value)

    def observe_ms(self, name: str, ms: float) -> None:
        with self._lock:
            t = self._timers.setdefault(name, _TimerAgg())
            t.observe(float(ms))

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            g = self._gauges.setdefault(name, _Gauge())
            g.value = float(value)

    def record_trade_slippage(self, symbol: str, slippage_bps: float) -> None:
        """Record slippage in basis points for a specific ticker."""
        self.set_gauge(f"slippage_bps_{symbol}", slippage_bps)
        self.inc(f"trades_total_{symbol}")

    def record_market_event(self, event_type: str) -> None:
        """Record market events like 'open', 'close', 'circuit_breaker'."""
        self.inc(f"market_event_{event_type}")

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            counters = {k: v.value for k, v in self._counters.items()}
            timers = {
                k: {
                    "count": v.count,
                    "total_ms": round(v.total_ms, 3),
                    "avg_ms": round(v.total_ms / v.count, 3) if v.count else 0.0,
                    "max_ms": round(v.max_ms, 3),
                }
                for k, v in self._timers.items()
            }
            gauges = {k: round(v.value, 6) for k, v in self._gauges.items()}
        return {
            "uptime_sec": int(time.time() - self._started_at),
            "counters": counters,
            "timers": timers,
            "gauges": gauges,
        }


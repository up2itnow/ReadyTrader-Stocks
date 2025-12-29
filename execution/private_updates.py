"""
Private order update helpers (Phase 2C).

ReadyTrader supports Binance private updates via websocket (see `execution/binance_user_stream.py`).
Most other exchanges require exchange-specific websocket auth flows (or CCXT Pro), which we avoid
to keep the OSS surface area lightweight.

As a pragmatic alternative, this module provides an **opt-in polling** mechanism that periodically
fetches open orders and emits simplified order update events.

Notes:
- Polling is not real-time and is subject to exchange rate limits.
- Intended for operator visibility and agent workflows that need “some” private updates without
  building a full private websocket stack for every exchange.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional, Tuple

from .cex_executor import CexExecutor


@dataclass(frozen=True)
class PrivateUpdateEvent:
    ts_ms: int
    exchange: str
    market_type: str
    symbol: Optional[str]
    order_id: str
    status: str
    filled: Optional[float]
    remaining: Optional[float]
    raw_order: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts_ms": self.ts_ms,
            "exchange": self.exchange,
            "market_type": self.market_type,
            "symbol": self.symbol,
            "order_id": self.order_id,
            "status": self.status,
            "filled": self.filled,
            "remaining": self.remaining,
            "order": self.raw_order,
        }


class CexPrivateOrderPoller:
    def __init__(
        self,
        *,
        exchange: str,
        market_type: str,
        symbol: str | None = None,
        poll_interval_sec: float = 2.0,
        max_events: int = 500,
    ) -> None:
        self.exchange = (exchange or "").strip().lower()
        self.market_type = (market_type or "spot").strip().lower()
        self.symbol = (symbol or "").strip().upper() or None
        self.poll_interval_sec = max(0.25, float(poll_interval_sec))

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None
        self._last_poll_at: Optional[float] = None
        self._events: Deque[Dict[str, Any]] = deque(maxlen=max(50, int(max_events)))

        # order_id -> snapshot of a few key fields we care about
        self._last_seen: Dict[str, Tuple[str, Optional[float], Optional[float]]] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            age = None
            if self._last_poll_at is not None:
                age = round(time.time() - self._last_poll_at, 3)
            return {
                "running": bool(self._thread and self._thread.is_alive()),
                "last_error": self._last_error,
                "last_poll_age_sec": age,
                "poll_interval_sec": self.poll_interval_sec,
                "symbol": self.symbol,
            }

    def list_events(self, *, limit: int = 100) -> list[Dict[str, Any]]:
        n = max(0, int(limit))
        with self._lock:
            return list(self._events)[-n:]

    def _run(self) -> None:  # pragma: no cover (network loop)
        while not self._stop.is_set():
            started = time.time()
            try:
                ex = CexExecutor(exchange_id=self.exchange, market_type=self.market_type, auth=True)
                orders = ex.fetch_open_orders(symbol=(self.symbol or None))
                normalized = [ex.normalize_order(o) for o in (orders or [])]
                now_ms = int(time.time() * 1000)

                with self._lock:
                    self._last_poll_at = time.time()
                    for o in normalized:
                        oid = str(o.get("id") or "")
                        if not oid:
                            continue
                        status = str(o.get("status") or "unknown")
                        filled = o.get("filled")
                        remaining = o.get("remaining")
                        prev = self._last_seen.get(oid)
                        snap = (status, filled, remaining)
                        if prev != snap:
                            self._last_seen[oid] = snap
                            evt = PrivateUpdateEvent(
                                ts_ms=now_ms,
                                exchange=self.exchange,
                                market_type=self.market_type,
                                symbol=self.symbol,
                                order_id=oid,
                                status=status,
                                filled=filled,
                                remaining=remaining,
                                raw_order=o,
                            )
                            self._events.append(evt.to_dict())

            except Exception as e:
                with self._lock:
                    self._last_error = str(e)

            # sleep (but allow fast shutdown)
            elapsed = time.time() - started
            sleep_for = max(0.0, self.poll_interval_sec - elapsed)
            self._stop.wait(timeout=sleep_for)


class CexPrivateUpdateManager:
    """
    Manage multiple polling-based private order update streams.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pollers: Dict[str, CexPrivateOrderPoller] = {}

    def _key(self, *, exchange: str, market_type: str, symbol: str | None) -> str:
        sym = (symbol or "").strip().upper()
        return f"{exchange}:{market_type}:{sym}"

    def start(
        self,
        *,
        exchange: str,
        market_type: str,
        symbol: str | None = None,
        poll_interval_sec: float = 2.0,
    ) -> None:
        ex = (exchange or "").strip().lower()
        mt = (market_type or "spot").strip().lower()
        sym = (symbol or "").strip().upper() or None
        k = self._key(exchange=ex, market_type=mt, symbol=sym)
        with self._lock:
            existing = self._pollers.get(k)
            if existing and existing.status().get("running"):
                return
            p = CexPrivateOrderPoller(
                exchange=ex,
                market_type=mt,
                symbol=sym,
                poll_interval_sec=poll_interval_sec,
            )
            self._pollers[k] = p
        p.start()

    def stop(self, *, exchange: str, market_type: str, symbol: str | None = None) -> None:
        ex = (exchange or "").strip().lower()
        mt = (market_type or "spot").strip().lower()
        sym = (symbol or "").strip().upper() or None
        k = self._key(exchange=ex, market_type=mt, symbol=sym)
        with self._lock:
            p = self._pollers.pop(k, None)
        if p:
            p.stop()

    def list_events(
        self,
        *,
        exchange: str,
        market_type: str,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        ex = (exchange or "").strip().lower()
        mt = (market_type or "spot").strip().lower()
        sym = (symbol or "").strip().upper() or None
        k = self._key(exchange=ex, market_type=mt, symbol=sym)
        with self._lock:
            p = self._pollers.get(k)
        return p.list_events(limit=limit) if p else []

    def status(self) -> Dict[str, Any]:
        with self._lock:
            items = list(self._pollers.items())
        return {k: p.status() for k, p in items}


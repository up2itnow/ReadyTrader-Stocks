from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from common.cache import TTLCache


@dataclass(frozen=True)
class TickerSnapshot:
    symbol: str
    last: float
    bid: Optional[float]
    ask: Optional[float]
    timestamp_ms: Optional[int]
    ingested_at_ms: int
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "last": self.last,
            "bid": self.bid,
            "ask": self.ask,
            "timestamp_ms": self.timestamp_ms,
            "ingested_at_ms": self.ingested_at_ms,
            "source": self.source,
        }


class InMemoryMarketDataStore:
    """
    In-memory store for externally-ingested market data.

    This is the main mechanism to support “user-provided feeds or MCPs”:
    - users/agents can fetch data elsewhere and push snapshots into ReadyTrader-Stocks via MCP tools
    - ReadyTrader-Stocks prefers ingested data when present and fresh
    """

    def __init__(self) -> None:
        self._tickers: TTLCache[Tuple[str], TickerSnapshot] = TTLCache(max_items=4096)
        self._ohlcv: TTLCache[Tuple[str, str, int], List[Any]] = TTLCache(max_items=1024)
        self._callbacks: List[callable] = []

    def subscribe(self, callback: callable) -> None:
        self._callbacks.append(callback)

    def put_ticker(
        self,
        *,
        symbol: str,
        last: float,
        bid: Optional[float],
        ask: Optional[float],
        timestamp_ms: Optional[int],
        source: str,
        ttl_sec: float,
    ) -> None:
        now_ms = int(time.time() * 1000)
        snap = TickerSnapshot(
            symbol=symbol.strip().upper(),
            last=float(last),
            bid=float(bid) if bid is not None else None,
            ask=float(ask) if ask is not None else None,
            timestamp_ms=int(timestamp_ms) if timestamp_ms is not None else None,
            ingested_at_ms=now_ms,
            source=source,
        )
        self._tickers.set((snap.symbol,), snap, ttl_seconds=float(ttl_sec))
        
        # Notify subscribers
        for cb in self._callbacks:
            try:
                cb(snap)
            except Exception:
                pass

    def get_ticker(self, *, symbol: str) -> Optional[TickerSnapshot]:
        return self._tickers.get((symbol.strip().upper(),))

    def put_ohlcv(self, *, symbol: str, timeframe: str, limit: int, ohlcv: List[Any], ttl_sec: float) -> None:
        key = (symbol.strip().upper(), timeframe.strip().lower(), int(limit))
        self._ohlcv.set(key, ohlcv, ttl_seconds=float(ttl_sec))

    def get_ohlcv(self, *, symbol: str, timeframe: str, limit: int) -> Optional[List[Any]]:
        key = (symbol.strip().upper(), timeframe.strip().lower(), int(limit))
        return self._ohlcv.get(key)

    def stats(self) -> Dict[str, Any]:
        # TTLCache doesn't expose internal stats; return minimal heartbeat
        return {"now_ms": int(time.time() * 1000)}


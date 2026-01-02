"""
Websocket-first market data streams for stocks.

This module provides **opt-in** background websocket clients for stock ticker streams:
- Alpaca (Primary stock data source)

Design notes:
- Streams run in a dedicated background thread per provider and use an asyncio loop
  within that thread (`asyncio.run`).
- The network loops are intentionally excluded from unit tests. Instead, parser functions are unit-tested.
- Parsed ticker snapshots are written into `InMemoryMarketDataStore` with short TTLs, so the MarketDataBus
  can prefer websocket data when it is fresh, and fall back to REST (yfinance/alpaca) when it is not.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import threading
import time
from typing import Any, Dict, List, Optional

import websockets

from .store import InMemoryMarketDataStore


class _MetricsLike:
    """
    Minimal interface for observability integration.
    """

    def inc(self, name: str, value: int = 1) -> None:  # pragma: no cover (interface)
        raise NotImplementedError

    def set_gauge(self, name: str, value: float) -> None:  # pragma: no cover (interface)
        raise NotImplementedError


def _split_symbol(symbol: str) -> str:
    """
    Clean up a stock symbol.
    ReadyTrader-Stocks uses standard ticker symbols (e.g., AAPL).
    """
    return (symbol or "").strip().upper()


def parse_alpaca_ticker_message(msg: Any) -> List[Dict[str, Any]]:
    """
    Parse Alpaca ticker messages (quotes or trades) into ticker snapshots.
    Typical format: [{"T": "q", "S": "AAPL", "bp": 150.1, "as": 150.2, "t": "2021-04-01T12:00:00Z"}]
    """
    if not isinstance(msg, list):
        return []

    results = []
    for item in msg:
        if not isinstance(item, dict):
            continue
        
        entry_type = item.get("T")
        symbol = item.get("S")
        if not symbol:
            continue

        if entry_type == "q":  # Quote
            results.append({
                "symbol": symbol,
                "bid": float(item.get("bp", 0)),
                "ask": float(item.get("ap", 0)),
                "last": float((item.get("bp", 0) + item.get("ap", 0)) / 2),
                "timestamp_ms": None  # Alpaca provides RFC3339, we can parse if needed
            })
        elif entry_type == "t":  # Trade
            results.append({
                "symbol": symbol,
                "last": float(item.get("p", 0)),
                "timestamp_ms": None
            })
    return results


class _WsStream:
    def __init__(self, *, metrics: _MetricsLike | None = None, metric_prefix: str = "ws") -> None:
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None
        self._last_message_at: Optional[float] = None
        self._metrics = metrics
        self._metric_prefix = metric_prefix

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._last_error = None
        if self._metrics:
            self._metrics.inc(f"{self._metric_prefix}_start_total", 1)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._metrics:
            self._metrics.inc(f"{self._metric_prefix}_stop_total", 1)

    def status(self) -> Dict[str, Any]:
        age = None
        if self._last_message_at is not None:
            age = round(time.time() - self._last_message_at, 3)
        if self._metrics and age is not None:
            self._metrics.set_gauge(f"{self._metric_prefix}_last_message_age_sec", float(age))
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "last_error": self._last_error,
            "last_message_age_sec": age,
        }

    def _run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except Exception as e:
            self._last_error = str(e)

    async def _run_async(self) -> None:  # pragma: no cover (network loop)
        raise NotImplementedError

    def _mark_message(self) -> None:
        self._last_message_at = time.time()
        if self._metrics:
            self._metrics.inc(f"{self._metric_prefix}_messages_total", 1)

    async def _sleep_backoff(self, backoff: float) -> None:
        b = max(0.1, float(backoff))
        jitter = 0.5 + (random.random() * 0.5)
        await asyncio.sleep(b * jitter)


class AlpacaTickerStream(_WsStream):
    def __init__(
        self,
        *,
        symbols: List[str],
        store: InMemoryMarketDataStore,
        metrics: _MetricsLike | None = None,
    ) -> None:
        super().__init__(metrics=metrics, metric_prefix="ws_alpaca")
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.paper_mode = os.getenv("PAPER_MODE", "true").lower() == "true"
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.store = store

    def _url(self) -> str:
        # IEX is the free feed
        return "wss://stream.data.alpaca.markets/v2/iex"

    async def _run_async(self) -> None:
        if not self.api_key or not self.api_secret:
            self._last_error = "Alpaca API credentials missing"
            return

        backoff = 1.0
        while not self._stop.is_set():
            try:
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_connect_total", 1)
                
                async with websockets.connect(self._url(), ping_interval=20, ping_timeout=20) as ws:
                    # 1. Receive welcome
                    await asyncio.wait_for(ws.recv(), timeout=10)
                    
                    # 2. Authenticate
                    auth_msg = {
                        "action": "auth",
                        "key": self.api_key,
                        "secret": self.api_secret
                    }
                    await ws.send(json.dumps(auth_msg))
                    
                    auth_resp = await asyncio.wait_for(ws.recv(), timeout=10)
                    auth_data = json.loads(auth_resp)
                    if auth_data[0].get("T") == "error":
                        self._last_error = f"Auth failed: {auth_data[0].get('msg')}"
                        await self._sleep_backoff(10)
                        continue

                    # 3. Subscribe
                    sub_msg = {
                        "action": "subscribe",
                        "quotes": self.symbols,
                        "trades": self.symbols
                    }
                    await ws.send(json.dumps(sub_msg))
                    
                    backoff = 1.0
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        snaps = parse_alpaca_ticker_message(msg)
                        
                        if not snaps:
                            continue
                            
                        self._mark_message()
                        for snap in snaps:
                            self.store.put_ticker(
                                symbol=snap["symbol"],
                                last=snap["last"],
                                bid=snap.get("bid"),
                                ask=snap.get("ask"),
                                timestamp_ms=snap.get("timestamp_ms"),
                                source="alpaca_ws",
                                ttl_sec=15.0,
                            )
            except Exception as e:
                self._last_error = str(e)
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_error_total", 1)
                await self._sleep_backoff(backoff)
                backoff = min(30.0, backoff * 2)


class WsStreamManager:
    """
    Manages background websocket ticker streams for stock brokerages.
    """

    def __init__(self, *, store: InMemoryMarketDataStore, metrics: _MetricsLike | None = None) -> None:
        self._store = store
        self._metrics = metrics
        self._lock = threading.Lock()
        self._streams: Dict[str, _WsStream] = {}

    def start(self, *, exchange: str, symbols: List[str], market_type: str = "stock") -> None:
        ex = (exchange or "").strip().lower()
        key = f"{ex}:{market_type}"
        self.stop(exchange=ex, market_type=market_type)
        
        if ex == "alpaca":
            s = AlpacaTickerStream(symbols=symbols, store=self._store, metrics=self._metrics)
        else:
            raise ValueError("Unsupported provider for websocket streams. Use 'alpaca'.")
            
        with self._lock:
            self._streams[key] = s
        s.start()

    def stop(self, *, exchange: str, market_type: str = "stock") -> None:
        key = f"{(exchange or '').strip().lower()}:{market_type}"
        with self._lock:
            s = self._streams.pop(key, None)
        if s:
            s.stop()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            items = list(self._streams.items())
        return {k: v.status() for k, v in items}

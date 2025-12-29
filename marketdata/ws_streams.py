"""
Websocket-first market data streams (Phase 2.5).

This module provides **opt-in** background websocket clients for public ticker streams:
- Binance (spot + swap/perp)
- Coinbase (spot)
- Kraken (spot)

Design notes:
- Streams run in a dedicated background thread per exchange+market_type key and use an asyncio loop
  within that thread (`asyncio.run`).
- The network loops are intentionally excluded from unit tests. Instead, parser functions are unit-tested.
- Parsed ticker snapshots are written into `InMemoryMarketDataStore` with short TTLs, so the MarketDataBus
  can prefer websocket data when it is fresh, and fall back to CCXT REST when it is not.
"""

from __future__ import annotations

import asyncio
import json
import random
import threading
import time
from datetime import datetime
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


def _split_symbol(symbol: str) -> tuple[str, str]:
    """
    Split a symbol into (base, quote).

    Supports:
    - BTC/USDT
    - BTC-USDT
    - BTC/USDT:USDT (ccxt swap notation; we ignore the suffix)
    """
    s = (symbol or "").strip().upper()
    if ":" in s:
        s = s.split(":", 1)[0]
    if "/" in s:
        base, quote = s.split("/", 1)
        return base, quote
    if "-" in s:
        base, quote = s.split("-", 1)
        return base, quote
    raise ValueError(f"Unsupported symbol format: {symbol}")


def _iso_to_ms(ts: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def _binance_stream_symbol(symbol: str) -> str:
    base, quote = _split_symbol(symbol)
    return f"{base}{quote}".lower()


def _coinbase_product_id(symbol: str) -> str:
    base, quote = _split_symbol(symbol)
    return f"{base}-{quote}"


def _kraken_pair(symbol: str) -> str:
    base, quote = _split_symbol(symbol)
    if base == "BTC":
        base = "XBT"
    return f"{base}/{quote}"


def parse_binance_ticker_message(msg: Dict[str, Any], *, stream_to_symbol: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Parse a Binance combined-stream ticker message into a ticker snapshot dict.

    Binance combined stream format:
      {"stream":"btcusdt@ticker","data":{...}}
    """
    data = msg.get("data") if isinstance(msg, dict) else None
    if not isinstance(data, dict):
        return None
    stream = str(msg.get("stream") or "")
    # stream is like: btcusdt@ticker
    stream_sym = stream.split("@", 1)[0].upper()
    symbol = stream_to_symbol.get(stream_sym)
    if not symbol:
        # fallback to data['s'] which is like BTCUSDT
        symbol = stream_to_symbol.get(str(data.get("s") or "").upper())
    if not symbol:
        return None
    try:
        last = float(data.get("c"))
        bid = float(data.get("b")) if data.get("b") is not None else None
        ask = float(data.get("a")) if data.get("a") is not None else None
        ts = int(data.get("E")) if data.get("E") is not None else None
        return {"symbol": symbol, "last": last, "bid": bid, "ask": ask, "timestamp_ms": ts}
    except Exception:
        return None


def parse_coinbase_ticker_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse a Coinbase (ws-feed) ticker message into a ticker snapshot dict.
    """
    if not isinstance(msg, dict):
        return None
    if msg.get("type") != "ticker":
        return None
    product_id = str(msg.get("product_id") or "")
    if not product_id:
        return None
    symbol = product_id.replace("-", "/").upper()
    try:
        last = float(msg.get("price"))
        bid = float(msg.get("best_bid")) if msg.get("best_bid") is not None else None
        ask = float(msg.get("best_ask")) if msg.get("best_ask") is not None else None
        ts = _iso_to_ms(str(msg.get("time") or ""))
        return {"symbol": symbol, "last": last, "bid": bid, "ask": ask, "timestamp_ms": ts}
    except Exception:
        return None


def parse_kraken_ticker_message(msg: Any) -> Optional[Dict[str, Any]]:
    """
    Parse a Kraken websocket ticker message into a ticker snapshot dict.
    """
    if not isinstance(msg, list) or len(msg) < 4:
        return None
    if msg[2] != "ticker":
        return None
    data = msg[1]
    pair = str(msg[3] or "")
    if not isinstance(data, dict) or not pair:
        return None
    # Convert XBT back to BTC for user-facing symbol
    symbol = pair.replace("XBT", "BTC").upper()
    try:
        last = float(data.get("c", [None])[0])
        bid = float(data.get("b", [None])[0]) if data.get("b") else None
        ask = float(data.get("a", [None])[0]) if data.get("a") else None
        return {"symbol": symbol, "last": last, "bid": bid, "ask": ask, "timestamp_ms": None}
    except Exception:
        return None


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
        # If the stream was previously stopped, allow restarting.
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
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:  # pragma: no cover (network loop)
        raise NotImplementedError

    def _mark_message(self) -> None:
        self._last_message_at = time.time()
        if self._metrics:
            self._metrics.inc(f"{self._metric_prefix}_messages_total", 1)

    async def _sleep_backoff(self, backoff: float) -> None:
        """
        Sleep with a little jitter to avoid synchronized reconnect storms.
        """
        b = max(0.1, float(backoff))
        jitter = 0.5 + (random.random() * 0.5)  # nosec B311 (non-crypto jitter)  # 0.5x .. 1.0x
        await asyncio.sleep(b * jitter)


class BinanceTickerStream(_WsStream):
    def __init__(
        self,
        *,
        symbols: List[str],
        market_type: str,
        store: InMemoryMarketDataStore,
        metrics: _MetricsLike | None = None,
    ) -> None:
        super().__init__(metrics=metrics, metric_prefix=f"ws_binance_{market_type}")
        self.exchange = "binance"
        self.market_type = market_type
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.store = store
        # map BTCUSDT -> BTC/USDT
        self.stream_to_symbol: Dict[str, str] = { _binance_stream_symbol(s).upper(): s for s in self.symbols }

    def _url(self) -> str:
        base = "wss://stream.binance.com:9443/stream"
        if self.market_type in {"swap", "perp"}:
            base = "wss://fstream.binance.com/stream"
        streams = "/".join([f"{_binance_stream_symbol(s)}@ticker" for s in self.symbols])
        return f"{base}?streams={streams}"

    async def _run_async(self) -> None:  # pragma: no cover
        backoff = 1.0
        while not self._stop.is_set():
            try:
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_connect_total", 1)
                async with websockets.connect(self._url(), ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        snap = parse_binance_ticker_message(msg, stream_to_symbol=self.stream_to_symbol)
                        if not snap:
                            if self._metrics:
                                self._metrics.inc(f"{self._metric_prefix}_parse_fail_total", 1)
                            continue
                        self._mark_message()
                        self.store.put_ticker(
                            symbol=snap["symbol"],
                            last=snap["last"],
                            bid=snap.get("bid"),
                            ask=snap.get("ask"),
                            timestamp_ms=snap.get("timestamp_ms"),
                            source=f"binance_ws_{self.market_type}",
                            ttl_sec=15.0,
                        )
            except Exception as e:
                self._last_error = str(e)
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_error_total", 1)
                await self._sleep_backoff(backoff)
                backoff = min(30.0, backoff * 2)


class CoinbaseTickerStream(_WsStream):
    def __init__(
        self,
        *,
        symbols: List[str],
        store: InMemoryMarketDataStore,
        metrics: _MetricsLike | None = None,
    ) -> None:
        super().__init__(metrics=metrics, metric_prefix="ws_coinbase_spot")
        self.exchange = "coinbase"
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.store = store
        self.product_ids = [_coinbase_product_id(s) for s in self.symbols]

    async def _run_async(self) -> None:  # pragma: no cover
        url = "wss://ws-feed.exchange.coinbase.com"
        sub = {"type": "subscribe", "product_ids": self.product_ids, "channels": ["ticker"]}
        backoff = 1.0
        while not self._stop.is_set():
            try:
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_connect_total", 1)
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    await ws.send(json.dumps(sub))
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        snap = parse_coinbase_ticker_message(msg)
                        if not snap:
                            if self._metrics:
                                self._metrics.inc(f"{self._metric_prefix}_parse_fail_total", 1)
                            continue
                        self._mark_message()
                        self.store.put_ticker(
                            symbol=snap["symbol"],
                            last=snap["last"],
                            bid=snap.get("bid"),
                            ask=snap.get("ask"),
                            timestamp_ms=snap.get("timestamp_ms"),
                            source="coinbase_ws_spot",
                            ttl_sec=15.0,
                        )
            except Exception as e:
                self._last_error = str(e)
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_error_total", 1)
                await self._sleep_backoff(backoff)
                backoff = min(30.0, backoff * 2)


class KrakenTickerStream(_WsStream):
    def __init__(
        self,
        *,
        symbols: List[str],
        store: InMemoryMarketDataStore,
        metrics: _MetricsLike | None = None,
    ) -> None:
        super().__init__(metrics=metrics, metric_prefix="ws_kraken_spot")
        self.exchange = "kraken"
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.store = store
        self.pairs = [_kraken_pair(s) for s in self.symbols]

    async def _run_async(self) -> None:  # pragma: no cover
        url = "wss://ws.kraken.com"
        sub = {"event": "subscribe", "pair": self.pairs, "subscription": {"name": "ticker"}}
        backoff = 1.0
        while not self._stop.is_set():
            try:
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_connect_total", 1)
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    await ws.send(json.dumps(sub))
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        snap = parse_kraken_ticker_message(msg)
                        if not snap:
                            if self._metrics:
                                self._metrics.inc(f"{self._metric_prefix}_parse_fail_total", 1)
                            continue
                        self._mark_message()
                        self.store.put_ticker(
                            symbol=snap["symbol"],
                            last=snap["last"],
                            bid=snap.get("bid"),
                            ask=snap.get("ask"),
                            timestamp_ms=snap.get("timestamp_ms"),
                            source="kraken_ws_spot",
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
    Manages background websocket ticker streams for top exchanges.

    Streams are opt-in: nothing starts automatically in order to keep CI/tests deterministic.
    """

    def __init__(self, *, store: InMemoryMarketDataStore, metrics: _MetricsLike | None = None) -> None:
        self._store = store
        self._metrics = metrics
        self._lock = threading.Lock()
        self._streams: Dict[str, _WsStream] = {}

    def start(self, *, exchange: str, symbols: List[str], market_type: str = "spot") -> None:
        ex = (exchange or "").strip().lower()
        key = f"{ex}:{market_type}"
        # Replace any existing stream for this (exchange, market_type) key to avoid duplicates.
        self.stop(exchange=ex, market_type=market_type)
        if ex == "binance":
            s = BinanceTickerStream(symbols=symbols, market_type=market_type, store=self._store, metrics=self._metrics)
        elif ex == "coinbase":
            s = CoinbaseTickerStream(symbols=symbols, store=self._store, metrics=self._metrics)
        elif ex == "kraken":
            s = KrakenTickerStream(symbols=symbols, store=self._store, metrics=self._metrics)
        else:
            raise ValueError("Unsupported exchange for websocket streams. Use one of: binance, coinbase, kraken")
        with self._lock:
            self._streams[key] = s
        s.start()

    def stop(self, *, exchange: str, market_type: str = "spot") -> None:
        key = f"{(exchange or '').strip().lower()}:{market_type}"
        with self._lock:
            s = self._streams.pop(key, None)
        if s:
            s.stop()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            items = list(self._streams.items())
        return {k: v.status() for k, v in items}


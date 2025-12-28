from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import websockets

from .store import InMemoryMarketDataStore


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
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def status(self) -> Dict[str, Any]:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "last_error": self._last_error,
        }

    def _run(self) -> None:
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:  # pragma: no cover (network loop)
        raise NotImplementedError


class BinanceTickerStream(_WsStream):
    def __init__(self, *, symbols: List[str], market_type: str, store: InMemoryMarketDataStore) -> None:
        super().__init__()
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
                async with websockets.connect(self._url(), ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        snap = parse_binance_ticker_message(msg, stream_to_symbol=self.stream_to_symbol)
                        if not snap:
                            continue
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
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2)


class CoinbaseTickerStream(_WsStream):
    def __init__(self, *, symbols: List[str], store: InMemoryMarketDataStore) -> None:
        super().__init__()
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
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    await ws.send(json.dumps(sub))
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        snap = parse_coinbase_ticker_message(msg)
                        if not snap:
                            continue
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
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2)


class KrakenTickerStream(_WsStream):
    def __init__(self, *, symbols: List[str], store: InMemoryMarketDataStore) -> None:
        super().__init__()
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
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    await ws.send(json.dumps(sub))
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        snap = parse_kraken_ticker_message(msg)
                        if not snap:
                            continue
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
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2)


class WsStreamManager:
    """
    Manages background websocket ticker streams for top exchanges.

    Streams are opt-in: nothing starts automatically in order to keep CI/tests deterministic.
    """

    def __init__(self, *, store: InMemoryMarketDataStore) -> None:
        self._store = store
        self._streams: Dict[str, _WsStream] = {}

    def start(self, *, exchange: str, symbols: List[str], market_type: str = "spot") -> None:
        ex = (exchange or "").strip().lower()
        key = f"{ex}:{market_type}"
        self.stop(exchange=ex, market_type=market_type)
        if ex == "binance":
            s = BinanceTickerStream(symbols=symbols, market_type=market_type, store=self._store)
        elif ex == "coinbase":
            s = CoinbaseTickerStream(symbols=symbols, store=self._store)
        elif ex == "kraken":
            s = KrakenTickerStream(symbols=symbols, store=self._store)
        else:
            raise ValueError("Unsupported exchange for websocket streams. Use one of: binance, coinbase, kraken")
        self._streams[key] = s
        s.start()

    def stop(self, *, exchange: str, market_type: str = "spot") -> None:
        key = f"{(exchange or '').strip().lower()}:{market_type}"
        s = self._streams.pop(key, None)
        if s:
            s.stop()

    def status(self) -> Dict[str, Any]:
        return {k: v.status() for k, v in self._streams.items()}


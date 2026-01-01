from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .exchange_provider import ExchangeProvider
from .store import InMemoryMarketDataStore, TickerSnapshot


class MarketDataProvider:
    provider_id: str

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        raise NotImplementedError

    def status(self) -> Dict[str, Any]:  # optional
        return {"provider_id": getattr(self, "provider_id", "unknown")}


def _to_timestamp_ms(ticker: Dict[str, Any]) -> Optional[int]:
    """
    Best-effort timestamp normalization from CCXT-style tickers.
    """
    ts = ticker.get("timestamp")
    if ts is not None:
        try:
            return int(ts)
        except Exception:
            return None
    # some feeds may already provide timestamp_ms
    ts2 = ticker.get("timestamp_ms")
    if ts2 is not None:
        try:
            return int(ts2)
        except Exception:
            return None
    return None


def _normalize_ticker_shape(
    *,
    symbol: str,
    last: float,
    bid: float | None,
    ask: float | None,
    timestamp_ms: int | None,
    source: str,
    is_mock: bool = False,
) -> Dict[str, Any]:
    return {
        "symbol": symbol.strip().upper(),
        "last": float(last),
        "bid": float(bid) if bid is not None else None,
        "ask": float(ask) if ask is not None else None,
        "timestamp_ms": int(timestamp_ms) if timestamp_ms is not None else None,
        "source": source,
        "is_mock": is_mock,
    }


@dataclass(frozen=True)
class IngestMarketDataProvider(MarketDataProvider):
    store: InMemoryMarketDataStore
    provider_id: str = "ingest"

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        snap: Optional[TickerSnapshot] = self.store.get_ticker(symbol=symbol)
        if not snap:
            raise ValueError("No ingested ticker available")
        ts_ms = snap.timestamp_ms if snap.timestamp_ms is not None else snap.ingested_at_ms
        out = _normalize_ticker_shape(
            symbol=snap.symbol,
            last=snap.last,
            bid=snap.bid,
            ask=snap.ask,
            timestamp_ms=ts_ms,
            source=snap.source,
        )
        out["ingested_at_ms"] = snap.ingested_at_ms
        return out

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        data = self.store.get_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        if data is None:
            raise ValueError("No ingested OHLCV available")
        return data


@dataclass(frozen=True)
class StockMarketDataProvider(MarketDataProvider):
    exchange_provider: ExchangeProvider
    provider_id: str = "yfinance"

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        # ExchangeProvider might not be async, but we can wrap it or assume it is if updated
        # Ideally ExchangeProvider itself should be refactored to use httpx or similar
        # For now, we remain compliant with the interface
        import asyncio
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, self.exchange_provider.fetch_ticker, symbol)
        # Ensure canonical keys for bus scoring.
        last = float(raw.get("last") or 0.0)
        bid = raw.get("bid")
        ask = raw.get("ask")
        ts_ms = _to_timestamp_ms(raw)
        out = _normalize_ticker_shape(
            symbol=str(raw.get("symbol") or symbol).strip().upper(),
            last=last,
            bid=float(bid) if bid is not None else None,
            ask=float(ask) if ask is not None else None,
            timestamp_ms=ts_ms,
            source=str(raw.get("exchange_id") or self.exchange_provider.get_exchange_name() or "ccxt").lower(),
            is_mock=raw.get("is_mock", False),
        )
        # Preserve raw for debugging.
        out["raw"] = raw
        return out

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.exchange_provider.fetch_ohlcv, symbol, timeframe, limit)

    def status(self) -> Dict[str, Any]:
        return self.exchange_provider.get_marketdata_capabilities()

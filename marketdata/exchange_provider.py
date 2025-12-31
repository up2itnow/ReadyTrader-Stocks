from __future__ import annotations
import logging

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import yfinance as yf
import pandas as pd

from common.cache import TTLCache
from common.errors import AppError

def _parse_timeframe_seconds(timeframe: str) -> Optional[int]:
    tf = timeframe.strip().lower()
    try:
        if tf.endswith("m"):
            return int(tf[:-1]) * 60
        if tf.endswith("h"):
            return int(tf[:-1]) * 3600
        if tf.endswith("d"):
            return int(tf[:-1]) * 86400
        if tf.endswith("w"):
            return int(tf[:-1]) * 7 * 86400
    except Exception:
        return None
    return None

def _seconds_to_next_boundary(period_sec: int) -> int:
    now = int(time.time())
    if period_sec <= 0:
        return 0
    return period_sec - (now % period_sec)

class ExchangeProvider:
    """
    Market-data connector layer (yfinance) for Stocks:
    - fetch_ticker (current info)
    - fetch_ohlcv (historical data)
    
    Design notes:
    - Replaces previous CCXT implementation.
    - Uses yfinance for data.
    - Caches results to avoid rate limits (though yfinance is lenient).
    """
    def __init__(self):
        self._ticker_cache: TTLCache[str, Dict[str, Any]] = TTLCache(max_items=2048)
        self._ohlcv_cache: TTLCache[Tuple[str, str, int], List[Any]] = TTLCache(max_items=1024)
        
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Stock symbols are straightforward (e.g. AAPL, MSFT).
        We just uppercase them.
        """
        return symbol.strip().upper()

    def get_marketdata_capabilities(self, exchange_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Return capability info.
        """
        return {
            "exchange_id": "yfinance",
            "has": {"fetchOHLCV": True, "fetchTicker": True},
            "timeframes": ["1m", "5m", "15m", "1h", "1d"],
            "symbols_count": "Unlimited",
            "proxy_configured": False,
            "default_type": "spot",
        }

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[Any]:
        """
        Fetch OHLCV data using yfinance.
        Mapped to CCXT cache format: [[timestamp, open, high, low, close, volume], ...]
        """
        ttl = float(os.getenv("OHLCV_CACHE_TTL_SEC", "60"))
        tf_sec = _parse_timeframe_seconds(timeframe)
        if tf_sec:
            ttl = min(ttl, float(_seconds_to_next_boundary(tf_sec) + 1))
            
        sym = self._normalize_symbol(symbol)
        cache_key = ("ohlcv", sym, timeframe, int(limit))
        cached = self._ohlcv_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            # yfinance interval mapping
            yf_interval = timeframe
            if timeframe == "1h": yf_interval = "1h"
            elif timeframe == "1d": yf_interval = "1d"
            elif timeframe == "1m": yf_interval = "1m"
            
            period = "1mo"
            if timeframe == '1m': period = "5d"
            if timeframe == '1d': period = "1y"

            ticker = yf.Ticker(sym)
            df = ticker.history(period=period, interval=yf_interval)
            
            if df.empty:
                raise AppError("data_not_found", f"No OHLCV history found for {sym} via yfinance.", {"symbol": sym})

            ohlcv = []
            for index, row in df.tail(limit).iterrows():
                ts = int(index.timestamp() * 1000)
                ohlcv.append([
                    ts,
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    float(row['Volume'])
                ])
                
            self._ohlcv_cache.set(cache_key, ohlcv, ttl_seconds=ttl)
            return ohlcv
            
        except AppError:
            raise
        except Exception as e:
            raise AppError("data_fetch_failed", f"yfinance OHLCV error for {sym}: {e}", {"symbol": sym})

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch ticker info (price).
        """
        ttl = float(os.getenv("TICKER_CACHE_TTL_SEC", "5"))
        sym = self._normalize_symbol(symbol)
        cache_key = ("ticker", sym)
        cached = self._ticker_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            
            if hist.empty:
                raise AppError("data_not_found", f"No price data found for {sym} via yfinance.", {"symbol": sym})

            last_row = hist.iloc[-1]
            price = float(last_row['Close'])
            open_px = float(last_row['Open'])
            high = float(last_row['High'])
            low = float(last_row['Low'])
            volume = float(last_row['Volume'])
            
            data = {
                "symbol": sym,
                "timestamp": int(time.time() * 1000),
                "datetime": pd.Timestamp.now().isoformat(),
                "high": high,
                "low": low,
                "bid": None,
                "ask": None,
                "vwap": None,
                "open": open_px,
                "close": price,
                "last": price,
                "previousClose": None,
                "change": None,
                "percentage": None,
                "average": None,
                "baseVolume": volume,
                "quoteVolume": None,
                "info": {},
                "is_mock": False
            }
            
            self._ticker_cache.set(cache_key, data, ttl_seconds=ttl)
            return data
        except AppError:
            raise
        except Exception as e:
            raise AppError("data_fetch_failed", f"yfinance ticker exception for {sym}: {e}", {"symbol": sym})

    def get_exchange_name(self) -> str:
        return "yfinance"

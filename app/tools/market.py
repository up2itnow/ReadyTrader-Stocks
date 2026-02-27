import json
from typing import Any, Dict, List

from fastmcp import FastMCP

from app.core.container import global_container


def _json_ok(data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": True, "data": data or {}}
    return json.dumps(payload, indent=2, sort_keys=True)


def _json_err(code: str, message: str, data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message, "data": data or {}}}
    return json.dumps(payload, indent=2, sort_keys=True)


def get_stock_price(symbol: str) -> str:
    """Fetch the latest real-time stock price (bid/ask/last)."""
    try:
        data = global_container.marketdata_bus.get_ticker(symbol)
        return _json_ok(data)
    except Exception as e:
        return _json_err("market_data_error", str(e), {"symbol": symbol})


def get_multiple_prices(symbols: List[str]) -> str:
    """Fetch real-time prices for multiple stock tickers simultaneously."""
    results = {}
    for sym in symbols:
        try:
            results[sym] = global_container.marketdata_bus.get_ticker(sym)
        except Exception:
            results[sym] = {"error": "could not fetch price"}
    return _json_ok({"prices": results})


def fetch_ohlcv(symbol: str, timeframe: str = '1d', limit: int = 100) -> str:
    """Fetch historical OHLCV candlestick data for technical analysis."""
    try:
        df = global_container.backtest_engine.fetch_ohlcv(symbol, timeframe, limit)
        data = df.reset_index().to_dict(orient="records")
        # Convert timestamps to string
        for d in data:
            if 'index' in d:
                d['timestamp'] = str(d.pop('index'))
            elif 'Date' in d:
                d['timestamp'] = str(d.pop('Date'))
        return _json_ok({"symbol": symbol, "timeframe": timeframe, "history": data})
    except Exception as e:
        return _json_err("history_error", str(e), {"symbol": symbol})


def register_market_tools(mcp: FastMCP):
    mcp.add_tool(get_stock_price)
    mcp.add_tool(get_multiple_prices)
    mcp.add_tool(fetch_ohlcv)

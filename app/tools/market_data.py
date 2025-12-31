import json
from typing import Any, Dict

from fastmcp import FastMCP

from app.core.container import global_container


def _json_ok(data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": True, "data": data or {}}
    return json.dumps(payload, indent=2, sort_keys=True)

def _json_err(code: str, message: str, data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message, "data": data or {}}}
    return json.dumps(payload, indent=2, sort_keys=True)

def register_market_tools(mcp: FastMCP):
    
    @mcp.tool()
    def get_market_sentiment() -> str:
        """Get the current Stock Market Fear & Greed Index."""
        from intelligence import get_market_sentiment
        return _json_ok({"sentiment": get_market_sentiment()})

    @mcp.tool()
    def get_market_news() -> str:
        """Get the latest public market news (Free RSS / Alpha Vantage)."""
        from intelligence import get_market_news
        return _json_ok({"news": get_market_news()})

    @mcp.tool()
    def fetch_rss_news(symbol: str = "") -> str:
        """Fetch stock market news from public RSS feeds (MarketWatch, Yahoo Finance). [FREE]"""
        from intelligence.core import fetch_rss_news
        return _json_ok({"news": fetch_rss_news(symbol)})

    @mcp.tool()
    def analyze_social_sentiment(symbol: str) -> str:
        """Analyze Reddit/X sentiment for a stock. (API Keys Required)."""
        from intelligence.core import analyze_social_sentiment
        return _json_ok({"sentiment": analyze_social_sentiment(symbol)})

    @mcp.tool()
    def fetch_financial_news(symbol: str) -> str:
        """Fetch high-tier financial news for a stock (NewsAPI required)."""
        from intelligence.core import fetch_financial_news
        return _json_ok({"news": fetch_financial_news(symbol)})

    @mcp.tool()
    async def get_stock_price(symbol: str, exchange: str = "alpaca") -> str:
        """
        Get the current price of a stock.
        """
        try:
            res = await global_container.marketdata_bus.fetch_ticker(symbol)
            ticker = res.data
            last_price = ticker.get("last")
            return _json_ok({
                "symbol": symbol, 
                "exchange": exchange, 
                "result": f"The current price of {symbol} is {last_price} (Source: {res.source})"
            })
        except Exception as e:
            return _json_err("fetch_price_error", str(e), {"symbol": symbol})

    @mcp.tool()
    async def get_multiple_prices(symbols: str) -> str:
        """
        Get prices for multiple stock symbols (comma-separated).
        """
        sym_list = [s.strip().upper() for s in symbols.split(",")]
        results = {}
        for sym in sym_list:
            try:
                res = await global_container.marketdata_bus.fetch_ticker(sym)
                results[sym] = res.data.get("last")
            except Exception:
                results[sym] = "Error"
        return _json_ok({"prices": results})

    @mcp.tool()
    def get_market_regime(symbol: str) -> str:
        """
        Detect the current market regime (Trending, Ranging, Volatile) for a stock.
        """
        try:
            df = global_container.backtest_engine.fetch_ohlcv(symbol, timeframe='1h', limit=100)
            regime = global_container.regime_detector.detect(df)
            return _json_ok({"symbol": symbol, "regime": regime})
        except Exception as e:
            return _json_err("regime_detection_error", str(e))

    @mcp.tool()
    async def fetch_ohlcv(symbol: str, timeframe: str = '1h', limit: int = 24) -> str:
        """
        Fetch historical OHLCV data.
        """
        try:
            res = await global_container.marketdata_bus.fetch_ohlcv(symbol, timeframe, limit)
            df = res.data
            return _json_ok(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "limit": limit,
                    "data": df.to_dict(orient="records") if hasattr(df, 'to_dict') else df,
                    "source": res.source
                }
            )
        except Exception as e:
            return _json_err("fetch_ohlcv_error", str(e))

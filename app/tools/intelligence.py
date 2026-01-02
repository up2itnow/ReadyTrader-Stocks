import json
from typing import Any, Dict

from fastmcp import FastMCP

from intelligence import get_market_sentiment as _get_mkt_sentiment
from intelligence import get_market_news as _get_mkt_news
from intelligence.core import fetch_rss_news as _fetch_rss
from intelligence.core import analyze_social_sentiment as _analyze_social
from intelligence.core import fetch_financial_news as _fetch_fin_news


def _json_ok(data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": True, "data": data or {}}
    return json.dumps(payload, indent=2, sort_keys=True)


def get_market_sentiment(symbol: str) -> str:
    """Analyze current market sentiment for a stock from news and social signals."""
    score = _get_mkt_sentiment(symbol)
    return _json_ok({"symbol": symbol, "sentiment_score": score})


def get_market_news(symbol: str) -> str:
    """Identify key market-moving news and headlines for a specific ticker."""
    news = _get_mkt_news(symbol)
    return _json_ok({"symbol": symbol, "news": news})


def fetch_rss_news(url: str) -> str:
    """Gather news headlines from a specific RSS feed URL."""
    news = _fetch_rss(url)
    return _json_ok({"url": url, "news": news})


def get_social_sentiment(symbol: str) -> str:
    """Analyze community sentiment for a stock ticker from social platforms (Reddit, Twitter)."""
    score = _analyze_social(symbol)
    return _json_ok({"symbol": symbol, "social_score": score})


def get_financial_news(symbol: str) -> str:
    """Retrieve detailed financial reports and official news for a ticker."""
    news = _fetch_fin_news(symbol)
    return _json_ok({"symbol": symbol, "financial_news": news})


def register_intelligence_tools(mcp: FastMCP):
    mcp.add_tool(get_market_sentiment)
    mcp.add_tool(get_market_news)
    mcp.add_tool(fetch_rss_news)
    mcp.add_tool(get_social_sentiment)
    mcp.add_tool(get_financial_news)

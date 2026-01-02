import json
from typing import Any, Dict

from fastmcp import FastMCP
from app.core.container import global_container
from core.stress_test import run_synthetic_stress_test as _run_stress


def _json_ok(data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": True, "data": data or {}}
    return json.dumps(payload, indent=2, sort_keys=True)


def _json_err(code: str, message: str, data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message, "data": data or {}}}
    return json.dumps(payload, indent=2, sort_keys=True)


def post_market_insight(symbol: str, agent_id: str, signal: str, confidence: float, reasoning: str, ttl_seconds: int = 3600) -> str:
    """Share a market insight or trade signal with other agents in the system."""
    insight = global_container.insight_store.post_insight(symbol, agent_id, signal, confidence, reasoning, ttl_seconds)
    return _json_ok({"insight": vars(insight)})


def get_latest_insights(symbol: str = "") -> str:
    """Retrieve recent high-confidence market insights for a specific symbol or all symbols."""
    insights = global_container.insight_store.get_latest_insights(symbol if symbol else None)
    return _json_ok({"insights": [vars(i) for i in insights]})


def run_backtest_simulation(strategy_code: str, symbol: str, timeframe: str = '1h') -> str:
    """Run a backtest of Python strategy code against historical historical data."""
    result = global_container.backtest_engine.run(strategy_code, symbol, timeframe)
    return _json_ok({"result": result})


def get_market_regime(symbol: str, timeframe: str = '1d') -> str:
    """Detect the prevailing market regime (TRENDING, RANGING, VOLATILE) for a stock."""
    try:
        df = global_container.backtest_engine.fetch_ohlcv(symbol, timeframe, limit=100)
        result = global_container.regime_detector.detect(df)
        return _json_ok({"symbol": symbol, "timeframe": timeframe, "result": result})
    except Exception as e:
        return _json_err("market_regime_error", str(e), {"symbol": symbol, "timeframe": timeframe})


def run_synthetic_stress_test(strategy_code: str, config_json: str = "{}") -> str:
    """
    Run a synthetic black-swan stress test on a strategy.
    Deterministic simulator that injects various market regimes and crashes.
    """
    try:
        config = json.loads(config_json)
        result = _run_stress(strategy_code, config)
        return _json_ok({"result": result})
    except Exception as e:
        return _json_err("stress_test_error", str(e))


def register_research_tools(mcp: FastMCP):
    mcp.add_tool(post_market_insight)
    mcp.add_tool(get_latest_insights)
    mcp.add_tool(run_backtest_simulation)
    mcp.add_tool(get_market_regime)
    mcp.add_tool(run_synthetic_stress_test)

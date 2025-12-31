import json
from typing import Any, Dict

from fastmcp import FastMCP

from app.core.config import settings
from app.core.container import global_container
from intelligence import get_cached_sentiment_score


def _json_ok(data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": True, "data": data or {}}
    return json.dumps(payload, indent=2, sort_keys=True)

def _json_err(code: str, message: str, data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message, "data": data or {}}}
    return json.dumps(payload, indent=2, sort_keys=True)

def register_trading_tools(mcp: FastMCP):
    
    @mcp.tool()
    def deposit_paper_funds(asset: str, amount: float) -> str:
        """[PAPER MODE] Deposit fake funds into the paper trading wallet."""
        if not settings.PAPER_MODE:
            return _json_err("paper_mode_required", "Paper mode is NOT enabled.")
        return _json_ok({"result": global_container.paper_engine.deposit("agent_zero", asset, amount)})

    @mcp.tool()
    def reset_paper_wallet() -> str:
        """[PAPER MODE] Reset the paper trading wallet and trade history."""
        if not settings.PAPER_MODE:
            return _json_err("paper_mode_required", "Paper mode is NOT enabled.")
        return _json_ok({"result": global_container.paper_engine.reset_wallet("agent_zero")})

    @mcp.tool()
    def validate_trade_risk(side: str, symbol: str, amount_usd: float, portfolio_value: float) -> str:
        """[GUARDIAN] Validate if a trade is safe to execute."""
        try:
            sentiment_score = get_cached_sentiment_score(symbol)
            daily_loss = 0.0
            drawdown = 0.0
            
            if settings.PAPER_MODE and global_container.paper_engine:
                 metrics = global_container.paper_engine.get_risk_metrics("agent_zero")
                 daily_loss = metrics.get('daily_pnl_pct', 0.0)
                 drawdown = metrics.get('drawdown_pct', 0.0)
            
            result = global_container.risk_guardian.validate_trade(
                side, symbol, amount_usd, portfolio_value, sentiment_score, daily_loss, drawdown
            )
            return _json_ok({
                "side": side,
                "symbol": symbol,
                "amount_usd": amount_usd,
                "result": result,
            })
        except Exception as e:
            return _json_err("risk_validation_error", str(e))

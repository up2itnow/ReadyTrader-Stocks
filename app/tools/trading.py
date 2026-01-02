import json
from typing import Any, Dict

from fastmcp import FastMCP

from app.core.compliance import global_compliance_ledger
from app.core.config import settings
from app.core.container import global_container
from intelligence import get_cached_sentiment_score


def _json_ok(data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": True, "data": data or {}}
    return json.dumps(payload, indent=2, sort_keys=True)


def _json_err(code: str, message: str, data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message, "data": data or {}}}
    return json.dumps(payload, indent=2, sort_keys=True)


def place_market_order(symbol: str, side: str, amount: float, rationale: str = "") -> str:
    """Place a market order for a stock."""
    return place_stock_order(symbol, side, amount, order_type="market", rationale=rationale)


def place_limit_order(symbol: str, side: str, amount: float, price: float, rationale: str = "") -> str:
    """Place a limit order for a stock."""
    return place_stock_order(symbol, side, amount, price=price, order_type="limit", rationale=rationale)


def deposit_paper_funds(asset: str, amount: float) -> str:
    """[PAPER MODE] Deposit virtual funds into the paper trading account."""
    if not settings.PAPER_MODE:
        return _json_err("invalid_mode", "Deposits only available in paper mode.")
    res = global_container.paper_engine.deposit("agent_zero", asset.upper(), amount)
    return _json_ok({"message": res})


def reset_paper_wallet() -> str:
    """[PAPER MODE] Clear all balances and trade history for the paper account."""
    if not settings.PAPER_MODE:
        return _json_err("invalid_mode", "Wallet reset only available in paper mode.")
    res = global_container.paper_engine.reset_wallet("agent_zero")
    return _json_ok({"message": res})


def validate_trade_risk(side: str, symbol: str, amount_usd: float, portfolio_value: float) -> str:
    """Verify if a trade complies with risk policies and current market conditions."""
    try:
        sentiment_score = get_cached_sentiment_score(symbol)
        daily_loss = 0.0
        drawdown = 0.0
        
        if settings.PAPER_MODE:
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


def start_brokerage_private_ws(brokerage: str) -> str:
    """Initiate a private websocket connection for order and portfolio updates."""
    if settings.PAPER_MODE:
        return _json_err("paper_mode_not_supported", "Private streams are not used in paper mode.")
    return _json_ok({"mode": "ws", "status": "connected", "brokerage": brokerage})


def place_stock_order(
    symbol: str, 
    side: str, 
    amount: float, 
    price: float = 0.0, 
    order_type: str = "market", 
    exchange: str = "alpaca", 
    rationale: str = "", 
    audit_context: str = ""
) -> str:
    # Compliance Record
    global_compliance_ledger.record_event("trade_start", {
        "symbol": symbol, "side": side, "amount": amount, "rationale": rationale, "audit_context": audit_context
    })
    
    # Risk Guardian Check
    try:
        portfolio_value = 100000.0
        sentiment_score = 0.0
        if settings.PAPER_MODE:
             metrics = global_container.paper_engine.get_risk_metrics("agent_zero")
             portfolio_value = metrics.get('equity', 100000.0)
        
        est_px = price if price > 0 else 1.0
        risk_result = global_container.risk_guardian.validate_trade(
            side=side, symbol=symbol, amount_usd=amount * est_px, portfolio_value=portfolio_value, sentiment_score=sentiment_score
        )
        
        if not risk_result.get("allowed", False):
            return _json_err("risk_blocked", risk_result.get("reason", "Risk policy violation"))
            
        if settings.EXECUTION_APPROVAL_MODE == "approve_each":
            proposal = global_container.execution_store.create(
                kind="stock_order",
                payload={
                    "symbol": symbol, "side": side, "amount": amount, "price": price,
                    "order_type": order_type, "rationale": rationale, "exchange": exchange
                }
            )
            return _json_ok({
                "status": "pending_approval",
                "request_id": proposal.request_id,
                "confirm_token": proposal.confirm_token,
                "order_details": proposal.payload
            })
            
    except Exception as e:
        return _json_err("risk_validation_error", str(e))

    # Execution
    if settings.PAPER_MODE:
        res = global_container.paper_engine.execute_trade(
            user_id="agent_zero", side=side, symbol=symbol, amount=amount,
            price=price if price > 0 else 0.0, rationale=rationale or "stock_order_paper"
        )
        return _json_ok({"venue": "paper", "result": res})
    
    try:
        global_container.policy_engine.validate_brokerage_order(
            exchange_id=exchange, symbol=symbol, side=side, amount=amount, market_type="spot"
        )
        ex = exchange.lower()
        if ex not in global_container.brokerages:
            return _json_err("brokerage_not_supported", f"Brokerage {exchange} not found.")
            
        brokerage = global_container.brokerages[ex]
        res = brokerage.place_order(symbol=symbol, side=side, qty=amount, order_type=order_type, price=price if price > 0 else None)
        return _json_ok({"venue": ex, "result": res})
    except Exception as e:
        return _json_err("execution_error", str(e))


def register_trading_tools(mcp: FastMCP):
    mcp.add_tool(place_market_order)
    mcp.add_tool(place_limit_order)
    mcp.add_tool(deposit_paper_funds)
    mcp.add_tool(reset_paper_wallet)
    mcp.add_tool(validate_trade_risk)
    mcp.add_tool(start_brokerage_private_ws)

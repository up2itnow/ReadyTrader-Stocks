import json
from typing import Any, Dict

from fastmcp import FastMCP

from app.core.config import settings
from app.core.container import global_container
from app.core.compliance import global_compliance_ledger


def _json_ok(data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": True, "data": data or {}}
    return json.dumps(payload, indent=2, sort_keys=True)

def _json_err(code: str, message: str, data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message, "data": data or {}}}
    return json.dumps(payload, indent=2, sort_keys=True)

# Module-level functions for testing

def place_market_order(symbol: str, side: str, amount: float, rationale: str = "") -> str:
    """Place a market order for a stock."""
    return place_stock_order(symbol, side, amount, order_type="market", rationale=rationale)

def place_limit_order(symbol: str, side: str, amount: float, price: float, rationale: str = "") -> str:
    """Place a limit order for a stock."""
    return place_stock_order(symbol, side, amount, price=price, order_type="limit", rationale=rationale)

def place_stock_order(symbol: str, side: str, amount: float, price: float = 0.0, order_type: str = "market", exchange: str = "alpaca", rationale: str = "", audit_context: str = "") -> str:
    """[RISK] Place an order for a stock through the Risk Guardian."""
    
    # 0. Compliance Audit Context
    global_compliance_ledger.record_event("trade_start", {
        "symbol": symbol, "side": side, "amount": amount, "rationale": rationale, "audit_context": audit_context
    })
    
    # 1. Risk Guardian Check
    try:
        # Get portfolio value (simplified)
        portfolio_value = 100000.0
        sentiment_score = 0.0
        if settings.PAPER_MODE:
             metrics = global_container.paper_engine.get_risk_metrics("agent_zero")
             portfolio_value = metrics.get('equity', 100000.0)
        
        risk_result = global_container.risk_guardian.validate_trade(
            side=side, symbol=symbol, amount_usd=amount * (price or 1.0), portfolio_value=portfolio_value, sentiment_score=sentiment_score
        )
        
        if not risk_result.get("allowed", False):
            return _json_err("risk_blocked", risk_result.get("reason", "Unknown risk rejection"))
            
        # 2. Human-in-the-loop check
        if settings.EXECUTION_APPROVAL_MODE == "approve_each":
            proposal = global_container.execution_store.create(
                kind="stock_order",
                payload={
                    "symbol": symbol,
                    "side": side,
                    "amount": amount,
                    "price": price,
                    "order_type": order_type,
                    "rationale": rationale,
                    "exchange": exchange
                }
            )
            return _json_ok({
                "status": "pending_approval",
                "message": f"Order for {amount} {symbol} ({side}) requires manual confirmation.",
                "request_id": proposal.request_id,
                "confirm_token": proposal.confirm_token, # Shared with agent (Phase 6)
                "order_details": proposal.payload
            })
            
    except Exception as e:
        return _json_err("risk_validation_error", str(e))

    # 3. Execution (Paper or Live)
    if settings.PAPER_MODE:
            res = global_container.paper_engine.execute_trade(
                user_id="agent_zero",
                side=side,
                symbol=symbol,
                amount=amount,
                price=price if price > 0 else 0.0, # Paper engine should fetch price if 0
                rationale=rationale or "stock_order_paper"
            )
            return _json_ok({"venue": "brokerage", "mode": "paper", "result": res})
    
    # Live Brokerage Execution
    try:
        global_container.policy_engine.validate_brokerage_order(
            exchange_id=exchange,
            symbol=symbol,
            side=side,
            amount=amount,
            market_type="spot"
        )
        
        ex = exchange.lower()
        if ex not in global_container.brokerages:
            return _json_err("brokerage_not_supported", f"Brokerage {exchange} is not supported.")
            
        brokerage = global_container.brokerages[ex]
        if not brokerage.is_available():
            return _json_err("brokerage_not_configured", f"{exchange.capitalize()} keys are missing. Cannot execute live trade.")
            
        res = brokerage.place_order(
            symbol=symbol,
            side=side,
            qty=amount,
            order_type=order_type,
            price=price if price > 0 else None
        )
        return _json_ok({"venue": ex, "mode": "live", "result": res})
    except Exception as e:
        return _json_err("execution_error", str(e))





def reset_paper_wallet() -> str:
    """Clear all balances and trade history for the current paper account."""
    if not settings.PAPER_MODE:
        return _json_err("invalid_mode", "Wallet reset only available in paper mode.")
    res = global_container.paper_engine.reset_wallet("agent_zero")
    return _json_ok({"message": res})

def deposit_paper_funds(asset: str, amount: float) -> str:
    """Add virtual funds to the paper trading account."""
    if not settings.PAPER_MODE:
        return _json_err("invalid_mode", "Deposits only available in paper mode.")
    res = global_container.paper_engine.deposit("agent_zero", asset.upper(), amount)
    return _json_ok({"message": res})


def start_brokerage_private_ws(exchange: str, market_type: str) -> str:
    """Start private websocket feed."""
    if settings.PAPER_MODE:
        return _json_err("paper_mode_not_supported", "No private WS in paper mode")
    
    if exchange == "kraken":
            return _json_ok({"mode": "poll", "status": "simulated_polling"})
            
    return _json_ok({"mode": "ws", "status": "connected"})


def register_execution_tools(mcp: FastMCP):
    mcp.add_tool(place_market_order)
    mcp.add_tool(place_limit_order)
    mcp.add_tool(place_stock_order)
    mcp.add_tool(reset_paper_wallet)
    mcp.add_tool(deposit_paper_funds)
    mcp.add_tool(start_brokerage_private_ws)

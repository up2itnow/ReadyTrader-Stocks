from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from execution.base import IBrokerage

# Conditional import to allow safe loading if dependencies missing
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
    _ALPACA_PY_AVAILABLE = True
except ImportError:
    _ALPACA_PY_AVAILABLE = False
    TradingClient = None
    OrderSide = None
    TimeInForce = None
    LimitOrderRequest = None
    MarketOrderRequest = None

class AlpacaBrokerage(IBrokerage):
    """
    Concrete implementation of a brokerage service using Alpaca-py SDK.
    Handles real order execution and account monitoring.
    """
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.paper_mode = os.getenv("PAPER_MODE", "true").lower() == "true"
        
        if not self.api_key or not self.api_secret or not _ALPACA_PY_AVAILABLE:
            self._available = False
            self.client = None
        else:
            self._available = True
            self.client = TradingClient(self.api_key, self.api_secret, paper=self.paper_mode)

    def is_available(self) -> bool:
        return self._available

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "market", price: Optional[float] = None) -> Dict[str, Any]:
        """
        Place a real order on Alpaca.
        """
        if not self._available or not self.client:
            raise RuntimeError("Alpaca API keys not configured or library missing.")

        try:
            req = None
            oside = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
            
            if order_type.lower() == "market":
                req = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=oside,
                    time_in_force=TimeInForce.GTC
                )
            elif order_type.lower() == "limit":
                if not price:
                    raise ValueError("Price required for limit order")
                req = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=oside,
                    time_in_force=TimeInForce.GTC,
                    limit_price=price
                )
            else:
                 raise ValueError(f"Unsupported order type: {order_type}")

            order = self.client.submit_order(order_data=req)
            
            return {
                "id": str(order.id),
                "client_order_id": str(order.client_order_id),
                "status": str(order.status),
                "symbol": order.symbol,
                "qty": float(order.qty) if order.qty else 0.0,
                "side": str(order.side),
                "type": str(order.type)
            }
        except Exception as e:
            raise RuntimeError(f"Alpaca order failure: {str(e)}")

    def get_account_balance(self) -> Dict[str, float]:
        """
        Fetch account equity and cash.
        """
        if not self._available or not self.client:
            raise RuntimeError("Alpaca API keys not configured.")
        
        try:
            account = self.client.get_account()
            return {
                "equity": float(account.equity or 0.0),
                "cash": float(account.cash or 0.0),
                "buying_power": float(account.buying_power or 0.0)
            }
        except Exception as e:
            raise RuntimeError(f"Alpaca account fetch failure: {str(e)}")

    def list_positions(self) -> List[Dict[str, Any]]:
        """
        List all open positions.
        """
        if not self._available or not self.client:
            raise RuntimeError("Alpaca API keys not configured.")
            
        try:
            positions = self.client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value or 0.0),
                    "avg_entry_price": float(p.avg_entry_price or 0.0),
                    "unrealized_pl": float(p.unrealized_pl or 0.0)
                }
                for p in positions
            ]
        except Exception as e:
            raise RuntimeError(f"Alpaca positions fetch failure: {str(e)}")

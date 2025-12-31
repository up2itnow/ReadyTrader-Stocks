from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
import alpaca_trade_api as tradeapi
from execution.base import IBrokerage

class AlpacaBrokerage(IBrokerage):
    """
    Concrete implementation of a brokerage service using Alpaca Trade API.
    Handles real order execution and account monitoring.
    """
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        
        if not self.api_key or not self.api_secret:
            self._available = False
        else:
            self._available = True
            self.api = tradeapi.REST(self.api_key, self.api_secret, self.base_url, api_version='v2')

    def is_available(self) -> bool:
        return self._available

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "market", price: Optional[float] = None) -> Dict[str, Any]:
        """
        Place a real order on Alpaca.
        """
        if not self._available:
            raise RuntimeError("Alpaca API keys not configured.")

        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force='gtc',
                limit_price=str(price) if price and order_type == 'limit' else None
            )
            return {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "status": order.status,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side,
                "type": order.type
            }
        except Exception as e:
            raise RuntimeError(f"Alpaca order failure: {str(e)}")

    def get_account_balance(self) -> Dict[str, float]:
        """
        Fetch account equity and cash.
        """
        if not self._available:
            raise RuntimeError("Alpaca API keys not configured.")
        
        try:
            account = self.api.get_account()
            return {
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power)
            }
        except Exception as e:
            raise RuntimeError(f"Alpaca account fetch failure: {str(e)}")

    def list_positions(self) -> List[Dict[str, Any]]:
        """
        List all open positions.
        """
        if not self._available:
            raise RuntimeError("Alpaca API keys not configured.")
            
        try:
            positions = self.api.list_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "avg_entry_price": float(p.avg_entry_price),
                    "unrealized_pl": float(p.unrealized_pl)
                }
                for p in positions
            ]
        except Exception as e:
            raise RuntimeError(f"Alpaca positions fetch failure: {str(e)}")

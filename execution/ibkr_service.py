from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from execution.base import IBrokerage

try:
    from ib_insync import IB, LimitOrder, MarketOrder, Stock
    _IB_AVAILABLE = True
except ImportError:
    _IB_AVAILABLE = False

class IBKRBrokerage(IBrokerage):
    """
    Interactive Brokers integration via ib_insync.
    Requires TWS or IB Gateway to be running.
    """
    def __init__(self):
        self.host = os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = int(os.getenv("IBKR_PORT", "7497")) # 7497 for TWS paper, 4002 for Gateway paper
        self.client_id = int(os.getenv("IBKR_CLIENT_ID", "1"))
        
        self.ib = None
        self._available = False
        
        if _IB_AVAILABLE and os.getenv("IBKR_ENABLED") == "true":
            self.ib = IB()
            # We don't connect in __init__ to avoid blocking, but mark as available for tool usage
            self._available = True

    def is_available(self) -> bool:
        return self._available and _IB_AVAILABLE

    def _ensure_connected(self):
        if self.ib and not self.ib.isConnected():
             self.ib.connect(self.host, self.port, clientId=self.client_id)

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "market", price: Optional[float] = None) -> Dict[str, Any]:
        if not self.is_available():
             raise RuntimeError("IBKR integration not enabled or ib_insync not installed.")
             
        self._ensure_connected()
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)
        
        if order_type == "market":
            order = MarketOrder(side.upper(), qty)
        elif order_type == "limit":
            order = LimitOrder(side.upper(), qty, price)
        else:
            raise ValueError(f"Unsupported order type: {order_type}")
            
        trade = self.ib.placeOrder(contract, order)
        return {
            "id": str(trade.order.orderId),
            "status": trade.orderStatus.status,
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "raw": str(trade.order)
        }

    def get_account_balance(self) -> Dict[str, float]:
        if not self.is_available():
             raise RuntimeError("IBKR integration not enabled.")
        
        self._ensure_connected()
        for v in self.ib.accountValues():
            if v.tag == 'NetLiquidation' and v.currency == 'USD':
                equity = float(v.value)
            if v.tag == 'CashBalance' and v.currency == 'USD':
                cash = float(v.value)
        
        return {
            "equity": equity if 'equity' in locals() else 0.0,
            "cash": cash if 'cash' in locals() else 0.0,
            "buying_power": equity * 4 if 'equity' in locals() else 0.0 # IBKR simplified
        }

    def list_positions(self) -> List[Dict[str, Any]]:
        if not self.is_available():
             raise RuntimeError("IBKR integration not enabled.")
             
        self._ensure_connected()
        return [
            {
                "symbol": p.contract.symbol,
                "qty": float(p.position),
                "avg_cost": float(p.avgCost)
            }
            for p in self.ib.positions()
        ]

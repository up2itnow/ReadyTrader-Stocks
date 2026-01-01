from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

from execution.base import IBrokerage


class TradierBrokerage(IBrokerage):
    """
    Tradier Brokerage integration.
    """
    def __init__(self):
        self.token = os.getenv("TRADIER_ACCESS_TOKEN")
        self.account_id = os.getenv("TRADIER_ACCOUNT_ID")
        self.sandbox = os.getenv("TRADIER_SANDBOX", "true").lower() == "true"
        self.base_url = "https://sandbox.tradier.com/v1" if self.sandbox else "https://api.tradier.com/v1"
        
        self._available = bool(self.token and self.account_id)

    def is_available(self) -> bool:
        return self._available

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "market", price: Optional[float] = None) -> Dict[str, Any]:
        if not self._available:
             raise RuntimeError("Tradier API keys not configured.")
             
        url = f"{self.base_url}/accounts/{self.account_id}/orders"
        data = {
            "class": "equity",
            "symbol": symbol,
            "side": side,  # buy, sell
            "quantity": qty,
            "type": order_type, # market, limit
            "duration": "day"
        }
        if order_type == "limit":
            data["price"] = price

        response = requests.post(url, data=data, headers=self._headers(), timeout=10)
        res_json = response.json()
        
        if response.status_code != 200:
            raise RuntimeError(f"Tradier order failure: {res_json}")
            
        order_info = res_json.get("order", {})
        return {
            "id": str(order_info.get("id")),
            "status": "submitted",
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "raw": res_json
        }

    def get_account_balance(self) -> Dict[str, float]:
        if not self._available:
             raise RuntimeError("Tradier API keys not configured.")
             
        url = f"{self.base_url}/accounts/{self.account_id}/balances"
        response = requests.get(url, headers=self._headers(), timeout=10)
        res_json = response.json()
        
        bal = res_json.get("balances", {})
        return {
            "equity": float(bal.get("total_equity", 0.0)),
            "cash": float(bal.get("total_cash", 0.0)),
            "buying_power": float(bal.get("buying_power", 0.0))
        }

    def list_positions(self) -> List[Dict[str, Any]]:
        if not self._available:
             raise RuntimeError("Tradier API keys not configured.")
             
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        response = requests.get(url, headers=self._headers(), timeout=10)
        res_json = response.json()
        
        positions = res_json.get("positions", {}).get("position", [])
        if isinstance(positions, dict): # Tradier returns a single dict if only one position
            positions = [positions]
            
        return [
            {
                "symbol": p.get("symbol"),
                "qty": float(p.get("quantity", 0.0)),
                "cost_basis": float(p.get("cost_basis", 0.0)),
                "date_acquired": p.get("date_acquired")
            }
            for p in positions
        ]

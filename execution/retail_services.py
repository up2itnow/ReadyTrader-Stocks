from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from execution.base import IBrokerage

# Conditional imports for optional dependencies
try:
    import robin_stocks.robinhood as rh
    _ROBINHOOD_LIB_AVAILABLE = True
except ImportError:
    _ROBINHOOD_LIB_AVAILABLE = False

try:
    from requests_oauthlib import OAuth1Session
    _OAUTH_LIB_AVAILABLE = True
except ImportError:
    _OAUTH_LIB_AVAILABLE = False

logger = logging.getLogger(__name__)

class SchwabBrokerage(IBrokerage):
    """
    Charles Schwab integration (Trader API).
    Requires 'SCHWAB_ACCESS_TOKEN' (Bearer) and 'SCHWAB_BASE_URL'.
    """
    def __init__(self):
        self.base_url = os.getenv("SCHWAB_BASE_URL", "https://api.schwabapi.com/trader/v1")
        self.access_token = os.getenv("SCHWAB_ACCESS_TOKEN")
        self._available = bool(self.access_token)

    def is_available(self) -> bool:
        return self._available

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "market", price: Optional[float] = None) -> Dict[str, Any]:
        if not self._available:
             raise RuntimeError("Schwab API not configured (missing SCHWAB_ACCESS_TOKEN).")
        
        # Schwab Order Format Construction
        # Note: This is a simplified representation of the complex Schwab order JSON
        instruction = "BUY" if side.lower() == "buy" else "SELL"
        asset_type = "EQUITY"
        
        payload = {
            "orderType": order_type.upper(),
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": qty,
                    "instrument": {
                        "symbol": symbol.upper(),
                        "assetType": asset_type
                    }
                }
            ]
        }
        
        if order_type.lower() == "limit" and price:
             payload["price"] = price
        
        # Account Number is usually required in the path
        account_hash = os.getenv("SCHWAB_ACCOUNT_HASH")
        if not account_hash:
            raise RuntimeError("SCHWAB_ACCOUNT_HASH is required for placing orders.")

        url = f"{self.base_url}/accounts/{account_hash}/orders"
        
        try:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=10)
            resp.raise_for_status()
            
            # Schwab returns 201 Created and location header usually, body might be empty
            location = resp.headers.get("Location", "")
            order_id = location.split("/")[-1] if location else "unknown"
            
            return {
                "id": order_id,
                "status": "submitted",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "venue": "schwab"
            }
        except Exception as e:
            logger.error(f"Schwab order failed: {e}")
            raise RuntimeError(f"Schwab order failure: {str(e)}")

    def get_account_balance(self) -> Dict[str, float]:
        if not self._available:
             raise RuntimeError("Schwab API not configured.")
        
        account_hash = os.getenv("SCHWAB_ACCOUNT_HASH")
        if not account_hash:
             # Try to list accounts to find one? For now fail.
             raise RuntimeError("SCHWAB_ACCOUNT_HASH required.")
             
        url = f"{self.base_url}/accounts/{account_hash}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            # Map Schwab fields (example structure)
            # securitiesAccount -> currentBalances -> liquidationValue, cashBalance
            agg = data.get("securitiesAccount", {}).get("currentBalances", {})
            return {
                "equity": float(agg.get("liquidationValue", 0.0)),
                "cash": float(agg.get("cashBalance", 0.0)),
                "buying_power": float(agg.get("buyingPower", 0.0))
            }
        except Exception as e:
            raise RuntimeError(f"Schwab balance fetch failed: {str(e)}")

    def list_positions(self) -> List[Dict[str, Any]]:
        if not self._available:
             raise RuntimeError("Schwab API not configured.")

        account_hash = os.getenv("SCHWAB_ACCOUNT_HASH")
        url = f"{self.base_url}/accounts/{account_hash}?fields=positions"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            positions_raw = data.get("securitiesAccount", {}).get("positions", [])
            out = []
            for p in positions_raw:
                inst = p.get("instrument", {})
                out.append({
                    "symbol": inst.get("symbol"),
                    "qty": float(p.get("longQuantity", 0.0)) - float(p.get("shortQuantity", 0.0)),
                    "avg_cost": float(p.get("averagePrice", 0.0)),
                    "market_value": float(p.get("marketValue", 0.0))
                })
            return out
        except Exception:
            return []


class EtradeBrokerage(IBrokerage):
    """
    E*TRADE integration via OAuth1.
    Requires Consumer Key/Secret and Oauth Resources.
    """
    def __init__(self):
        self.consumer_key = os.getenv("ETRADE_CONSUMER_KEY")
        self.consumer_secret = os.getenv("ETRADE_CONSUMER_SECRET")
        self.resource_owner_key = os.getenv("ETRADE_RESOURCE_OWNER_KEY") # Access Token
        self.resource_owner_secret = os.getenv("ETRADE_RESOURCE_OWNER_SECRET") # Access Secret
        
        self.base_url = "https://api.etrade.com/v1/market" # Prod
        if os.getenv("ETRADE_SANDBOX") == "true":
            self.base_url = "https://apisb.etrade.com/v1/market"
            
        self._available = bool(
            self.consumer_key and self.consumer_secret and 
            self.resource_owner_key and self.resource_owner_secret and 
            _OAUTH_LIB_AVAILABLE
        )
        
        self.session = None
        if self._available:
            self.session = OAuth1Session(
                self.consumer_key,
                client_secret=self.consumer_secret,
                resource_owner_key=self.resource_owner_key,
                resource_owner_secret=self.resource_owner_secret
            )

    def is_available(self) -> bool:
        return self._available

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "market", price: Optional[float] = None) -> Dict[str, Any]:
        if not self.session:
            raise RuntimeError("Etrade not configured or dependencies missing.")
            
        account_id_key = os.getenv("ETRADE_ACCOUNT_ID_KEY")
        if not account_id_key:
             raise RuntimeError("ETRADE_ACCOUNT_ID_KEY required.")

        # Etrade Preview -> Place flow is typical, here we assume direct Place structure for brevity
        # OR we just implement Preview? Real wiring implies Place.
        # Etrade XML/JSON structure is complex.
        
        action = "BUY" if side.lower() == "buy" else "SELL"
        price_type = "MARKET" if order_type == "market" else "LIMIT"
        
        payload = {
            "PlaceOrderRequest": {
                "Order": {
                    "Instrument": {
                        "Product": {"securityType": "EQ", "symbol": symbol.upper()},
                        "orderAction": action,
                        "quantityType": "QUANTITY",
                        "quantity": int(qty)
                    },
                    "priceType": price_type,
                    "orderTerm": "GOOD_FOR_DAY",
                    "marketSession": "REGULAR"
                }
            }
        }
        if price:
            payload["PlaceOrderRequest"]["Order"]["limitPrice"] = price

        # We need the URL for accounts
        url = f"https://api.etrade.com/v1/accounts/{account_id_key}/orders/place.json"
        if os.getenv("ETRADE_SANDBOX") == "true":
             url = f"https://apisb.etrade.com/v1/accounts/{account_id_key}/orders/place.json"

        try:
            resp = self.session.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            
            # Parse OrderId
            try:
                order_id = data["PlaceOrderResponse"]["OrderIds"][0]["orderId"]
            except (KeyError, IndexError):
                order_id = "unknown"
                
            return {
                "id": str(order_id),
                "status": "submitted",
                "symbol": symbol,
                "qty": qty,
                "venue": "etrade"
            }
        except Exception as e:
            raise RuntimeError(f"Etrade order failed: {str(e)}")

    def get_account_balance(self) -> Dict[str, float]:
        if not self.session:
             return {"equity": 0.0, "cash": 0.0}
        
        account_id_key = os.getenv("ETRADE_ACCOUNT_ID_KEY")
        url = f"https://api.etrade.com/v1/accounts/{account_id_key}/balance.json"
        
        try:
            resp = self.session.get(url, params={"instType": "BROKERAGE"})
            resp.raise_for_status()
            d = resp.json().get("BalanceResponse", {})
            real = d.get("RealTimeValues", {})
            computed = d.get("Computed", {})
            
            return {
                "equity": float(real.get("totalAccountValue", 0.0)),
                "cash": float(computed.get("cashAvailableForInvestment", 0.0)),
                "buying_power": float(computed.get("netCash", 0.0))
            }
        except Exception:
            return {"equity": 0.0, "cash": 0.0}

    def list_positions(self) -> List[Dict[str, Any]]:
        return []

class RobinhoodBrokerage(IBrokerage):
    """
    Robinhood via 'robin_stocks'.
    Requires ROBINHOOD_USER and ROBINHOOD_PASS.
    MFA may be tricky - supports ROBINHOOD_MFA_CODE (if static) or TOTP secret.
    """
    def __init__(self):
        self.user = os.getenv("ROBINHOOD_USER")
        self.password = os.getenv("ROBINHOOD_PASS")
        self.totp = os.getenv("ROBINHOOD_TOTP")
        self._available = bool(self.user and self.password and _ROBINHOOD_LIB_AVAILABLE)
        self._logged_in = False

    def is_available(self) -> bool:
        return self._available

    def _ensure_login(self):
        if not self._available:
             raise RuntimeError("Robinhood not configured or library missing.")
        if self._logged_in:
            return
            
        # Try login
        try:
            # If TOTP is provided, it handles 2FA auto-generation
            rh.login(username=self.user, password=self.password, mfa_code=self.totp)
            self._logged_in = True
        except Exception as e:
            raise RuntimeError(f"Robinhood login failed: {str(e)}")

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "market", price: Optional[float] = None) -> Dict[str, Any]:
        self._ensure_login()
        
        try:
            if side.lower() == "buy":
                if order_type == "market":
                    res = rh.orders.order_buy_market(symbol, qty)
                else:
                    res = rh.orders.order_buy_limit(symbol, qty, price)
            else:
                if order_type == "market":
                    res = rh.orders.order_sell_market(symbol, qty)
                else:
                    res = rh.orders.order_sell_limit(symbol, qty, price)
            
            # Robin_stocks returns a dict with 'id', 'state', etc.
            if not res or 'id' not in res:
                raise RuntimeError(f"Order failed or returned empty: {res}")
                
            return {
                "id": res.get("id"),
                "status": res.get("state"),
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "venue": "robinhood"
            }
        except Exception as e:
            raise RuntimeError(f"Robinhood execution error: {str(e)}")

    def get_account_balance(self) -> Dict[str, float]:
        self._ensure_login()
        try:
            profile = rh.profiles.load_account_profile()
            # 'portfolio_cash', 'buying_power'
            cash = float(profile.get("portfolio_cash", 0.0))
            bp = float(profile.get("buying_power", 0.0))
            
            # For equity, we need holdings or portfolio call
            # This is an approximation
            equity = cash # simplification if positions not summed
            
            return {
                "equity": equity,
                "cash": cash,
                "buying_power": bp
            }
        except Exception as e:
            raise RuntimeError(f"Robinhood balance error: {str(e)}")

    def list_positions(self) -> List[Dict[str, Any]]:
        self._ensure_login()
        try:
            positions = rh.account.build_holdings()
            # returns dict: {'AAPL': {'price': ..., 'quantity': ...}}
            out = []
            for sym, data in positions.items():
                out.append({
                    "symbol": sym,
                    "qty": float(data.get("quantity", 0.0)),
                    "avg_cost": float(data.get("average_buy_price", 0.0)),
                    "equity": float(data.get("equity", 0.0))
                })
            return out
        except Exception:
            return []

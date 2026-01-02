from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


@dataclass
class PolicyError(Exception):
    code: str
    message: str
    data: Dict[str, Any]


def _parse_csv_set(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    return {v.strip().lower() for v in value.split(",") if v.strip()}


def _env_float(name: str, default: Optional[float] = None) -> Optional[float]:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class PolicyEngine:
    """
    Policy enforcement for live brokerage execution.

    Philosophy:
    - The policy engine is a deterministic “deny layer”.
    - Rules are only enforced if allowlist/limit env vars are set.
    """

    def __init__(self) -> None:
        pass

    def validate_insight_backing(self, *, symbol: str, insight_id: str, insights: List[Any]) -> float:
        """
        Verify that a trade is backed by a high-confidence insight.
        """
        if not insight_id:
            return 0.0
            
        sym = symbol.strip().upper()
        for ins in insights:
            ins_id = getattr(ins, "insight_id", None) or ins.get("insight_id")
            ins_sym = getattr(ins, "symbol", None) or ins.get("symbol")
            if ins_id == insight_id and ins_sym == sym:
                conf = getattr(ins, "confidence", 0.0) or ins.get("confidence", 0.0)
                return float(conf)
        
        raise PolicyError(
            code="insight_not_found",
            message=f"No valid insight found for {symbol} with ID {insight_id}",
            data={"symbol": symbol, "insight_id": insight_id}
        )

    def validate_brokerage_order(
        self,
        *,
        exchange_id: str,
        symbol: str,
        market_type: str = "spot",
        side: str,
        amount: float,
        order_type: str,
        price: Optional[float] = None,
        overrides: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Validate a brokerage order against configured limits and allowlists.
        """
        ex = exchange_id.strip().lower()
        sym = symbol.strip().upper()
        sd = side.strip().lower()
        ot = order_type.strip().lower()

        allow_exchanges = _parse_csv_set(os.getenv("ALLOW_BROKERAGES"))
        if allow_exchanges and ex not in allow_exchanges:
            raise PolicyError(
                code="brokerage_not_allowed",
                message=f"Brokerage '{exchange_id}' is not allowlisted.",
                data={"brokerage": exchange_id, "allow_brokerages": sorted(allow_exchanges)},
            )

        allow_symbols = _parse_csv_set(os.getenv("ALLOW_TICKERS"))
        if allow_symbols and sym.lower() not in allow_symbols:
            raise PolicyError(
                code="ticker_not_allowed",
                message=f"Ticker '{symbol}' is not allowlisted.",
                data={"symbol": symbol, "allow_tickers": sorted(allow_symbols)},
            )

        if sd not in {"buy", "sell"}:
            raise PolicyError("invalid_side", "side must be 'buy' or 'sell'", {"side": side})
        
        if ot not in {"market", "limit"}:
            raise PolicyError(
                "invalid_order_type",
                "order_type must be 'market' or 'limit'",
                {"order_type": order_type},
            )
            
        if amount <= 0:
            raise PolicyError("invalid_amount", "amount must be > 0", {"amount": amount})
            
        if ot == "limit" and (price is None or price <= 0):
            raise PolicyError("invalid_price", "price must be provided for limit orders", {"price": price})

        max_amt = (overrides or {}).get("MAX_ORDER_AMOUNT", _env_float("MAX_ORDER_AMOUNT", None))
        if max_amt is not None and amount > max_amt:
            raise PolicyError(
                code="order_amount_too_large",
                message=f"Order amount {amount} exceeds MAX_ORDER_AMOUNT={max_amt}.",
                data={"amount": amount, "max_order_amount": max_amt},
            )

    def validate_brokerage_access(self, *, exchange_id: str) -> None:
        """Simple check if a brokerage is allowed."""
        ex = exchange_id.strip().lower()
        allow = _parse_csv_set(os.getenv("ALLOW_BROKERAGES"))
        if allow and ex not in allow:
            raise PolicyError(
                code="brokerage_not_allowed",
                message=f"Brokerage '{exchange_id}' is not allowlisted.",
                data={"brokerage": exchange_id, "allow_brokerages": sorted(allow)},
            )

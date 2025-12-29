from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


def normalize_market_type(market_type: str | None) -> str:
    """
    Normalize user-provided market type names into a small canonical set.

    Canonical values:
    - spot
    - swap (perpetuals)
    - future
    - auto (let the connector infer)
    """
    mt = (market_type or "").strip().lower()
    if not mt:
        return "spot"
    if mt in {"perp", "perps", "perpetual", "perpetuals"}:
        return "swap"
    if mt in {"spot", "swap", "future", "auto"}:
        return mt
    return mt


def normalize_order_status(raw_status: Any) -> str:
    """
    Normalize exchange/ccxt status strings into a small stable set.

    Returns one of:
    - open
    - filled
    - canceled
    - rejected
    - unknown
    """
    s = str(raw_status or "").strip().lower()
    # Many exchanges use these variants for "open but not done".
    if s in {"open", "new", "partially_filled", "partial", "partially-filled", "partial_fill", "partiallyfilled"}:
        return "open"
    if s in {"closed", "filled", "done"}:
        return "filled"
    if s in {"canceled", "cancelled", "expired"}:
        return "canceled"
    if s in {"rejected"}:
        return "rejected"
    return "unknown"


@dataclass(frozen=True)
class NormalizedOrder:
    """
    Cross-exchange order shape suitable for MCP tool output and unit tests.

    Notes:
    - Most fields are optional because exchanges vary widely.
    - We preserve raw payload for debugging (but do not log secrets).
    """

    exchange: str
    id: Optional[str]
    client_order_id: Optional[str]
    symbol: str
    market_type: str
    side: str
    order_type: str
    status: str
    amount: Optional[float]
    filled: Optional[float]
    remaining: Optional[float]
    price: Optional[float]
    average: Optional[float]
    cost: Optional[float]
    timestamp: Optional[int]
    raw: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "id": self.id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "market_type": self.market_type,
            "side": self.side,
            "order_type": self.order_type,
            "status": self.status,
            "amount": self.amount,
            "filled": self.filled,
            "remaining": self.remaining,
            "price": self.price,
            "average": self.average,
            "cost": self.cost,
            "timestamp": self.timestamp,
            "raw": self.raw,
        }


def normalize_ccxt_order(*, exchange: str, market_type: str, order: Dict[str, Any]) -> NormalizedOrder:
    """
    Convert a CCXT order dict to our stable `NormalizedOrder`.
    """
    mt = normalize_market_type(market_type)
    # Some exchanges omit fields; do lightweight derivation where safe.
    amount = order.get("amount")
    filled = order.get("filled")
    remaining = order.get("remaining")
    try:
        if remaining is None and amount is not None and filled is not None:
            remaining = float(amount) - float(filled)
    except Exception:
        remaining = order.get("remaining")
    return NormalizedOrder(
        exchange=exchange,
        id=str(order.get("id")) if order.get("id") is not None else None,
        client_order_id=(
            str(order.get("clientOrderId")) if order.get("clientOrderId") is not None else None
        ),
        symbol=str(order.get("symbol") or ""),
        market_type=mt,
        side=str(order.get("side") or "").lower(),
        order_type=str(order.get("type") or "").lower(),
        status=normalize_order_status(order.get("status")),
        amount=amount,
        filled=filled,
        remaining=remaining,
        price=order.get("price"),
        average=order.get("average"),
        cost=order.get("cost"),
        timestamp=order.get("timestamp"),
        raw=order,
    )


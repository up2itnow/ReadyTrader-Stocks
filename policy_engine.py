from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set


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
    Phase 1 policy enforcement for live execution.

    Defaults are permissive (no allowlists) unless env vars are set.

    Philosophy:
    - The policy engine is a deterministic “deny layer” (it never forces trades).
    - If an allowlist/limit env var is set, it is enforced strictly.
    - If unset, the rule is not applied (so dev/demo works out of the box).
    """

    def __init__(self) -> None:
        # Intentionally stateless in Phase 1
        pass

    def validate_swap(
        self,
        *,
        chain: str,
        from_token: str,
        to_token: str,
        amount: float,
        overrides: Optional[Dict[str, float]] = None,
    ) -> None:
        chain_l = chain.strip().lower()
        from_l = from_token.strip().lower()
        to_l = to_token.strip().lower()

        allow_chains = _parse_csv_set(os.getenv("ALLOW_CHAINS"))
        if allow_chains and chain_l not in allow_chains:
            raise PolicyError(
                code="chain_not_allowed",
                message=f"Chain '{chain}' is not allowlisted.",
                data={"chain": chain, "allow_chains": sorted(allow_chains)},
            )

        allow_tokens = _parse_csv_set(os.getenv("ALLOW_TOKENS"))
        if allow_tokens:
            if from_l not in allow_tokens or to_l not in allow_tokens:
                raise PolicyError(
                    code="token_not_allowed",
                    message="Token not allowlisted.",
                    data={
                        "from_token": from_token,
                        "to_token": to_token,
                        "allow_tokens": sorted(allow_tokens),
                    },
                )

        max_amount_global = (overrides or {}).get("MAX_TRADE_AMOUNT", _env_float("MAX_TRADE_AMOUNT", None))
        if max_amount_global is not None and amount > max_amount_global:
            raise PolicyError(
                code="trade_amount_too_large",
                message=f"Trade amount {amount} exceeds MAX_TRADE_AMOUNT={max_amount_global}.",
                data={"amount": amount, "max_trade_amount": max_amount_global},
            )

        max_amount_from = _env_float(f"MAX_TRADE_AMOUNT_{from_token.strip().upper()}", None)
        if max_amount_from is not None and amount > max_amount_from:
            raise PolicyError(
                code="trade_amount_too_large",
                message=(
                    f"Trade amount {amount} {from_token} exceeds "
                    f"MAX_TRADE_AMOUNT_{from_token.strip().upper()}={max_amount_from}."
                ),
                data={"amount": amount, "token": from_token, "max_trade_amount_token": max_amount_from},
            )

    def validate_transfer_native(
        self,
        *,
        chain: str,
        to_address: str,
        amount: float,
        overrides: Optional[Dict[str, float]] = None,
    ) -> None:
        chain_l = chain.strip().lower()

        allow_chains = _parse_csv_set(os.getenv("ALLOW_CHAINS"))
        if allow_chains and chain_l not in allow_chains:
            raise PolicyError(
                code="chain_not_allowed",
                message=f"Chain '{chain}' is not allowlisted.",
                data={"chain": chain, "allow_chains": sorted(allow_chains)},
            )

        max_transfer = (overrides or {}).get("MAX_TRANSFER_NATIVE", _env_float("MAX_TRANSFER_NATIVE", None))
        if max_transfer is not None and amount > max_transfer:
            raise PolicyError(
                code="transfer_amount_too_large",
                message=f"Transfer amount {amount} exceeds MAX_TRANSFER_NATIVE={max_transfer}.",
                data={"amount": amount, "max_transfer_native": max_transfer},
            )

        allow_to = _parse_csv_set(os.getenv("ALLOW_TO_ADDRESSES"))
        if allow_to and to_address.strip().lower() not in allow_to:
            raise PolicyError(
                code="recipient_not_allowed",
                message="Recipient address is not allowlisted.",
                data={"to_address": to_address, "allow_to_addresses": sorted(allow_to)},
            )

    def validate_router_address(self, *, chain: str, router_address: str, context: Dict[str, Any]) -> None:
        """
        Validate that the DEX router / spender is allowlisted, if allowlists are configured.
        """
        addr = router_address.strip().lower()
        chain_l = chain.strip().lower()

        allow_global = _parse_csv_set(os.getenv("ALLOW_ROUTERS"))
        allow_chain = _parse_csv_set(os.getenv(f"ALLOW_ROUTERS_{chain_l.upper()}"))
        allow = allow_chain or allow_global

        if allow and addr not in allow:
            raise PolicyError(
                code="router_not_allowed",
                message="Router/spender address is not allowlisted.",
                data={"router": router_address, "chain": chain, "allow_routers": sorted(allow), "context": context},
            )

    def validate_cex_order(
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
        ex = exchange_id.strip().lower()
        sym = symbol.strip().upper()
        mt = (market_type or "").strip().lower() or "spot"
        sd = side.strip().lower()
        ot = order_type.strip().lower()

        allow_exchanges = _parse_csv_set(os.getenv("ALLOW_EXCHANGES"))
        if allow_exchanges and ex not in allow_exchanges:
            raise PolicyError(
                code="exchange_not_allowed",
                message=f"Exchange '{exchange_id}' is not allowlisted.",
                data={"exchange": exchange_id, "allow_exchanges": sorted(allow_exchanges)},
            )

        allow_symbols = _parse_csv_set(os.getenv("ALLOW_CEX_SYMBOLS"))
        if allow_symbols and sym.lower() not in allow_symbols:
            raise PolicyError(
                code="symbol_not_allowed",
                message=f"Symbol '{symbol}' is not allowlisted for CEX.",
                data={"symbol": symbol, "allow_cex_symbols": sorted(allow_symbols)},
            )

        allow_market_types = _parse_csv_set(os.getenv("ALLOW_CEX_MARKET_TYPES"))
        if allow_market_types and mt not in allow_market_types:
            raise PolicyError(
                code="market_type_not_allowed",
                message=f"Market type '{market_type}' is not allowlisted for CEX.",
                data={"market_type": market_type, "allow_cex_market_types": sorted(allow_market_types)},
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
            raise PolicyError("invalid_price", "price must be provided for limit orders and be > 0", {"price": price})

        max_amt = (overrides or {}).get("MAX_CEX_ORDER_AMOUNT", _env_float("MAX_CEX_ORDER_AMOUNT", None))
        if max_amt is not None and amount > max_amt:
            raise PolicyError(
                code="order_amount_too_large",
                message=f"Order amount {amount} exceeds MAX_CEX_ORDER_AMOUNT={max_amt}.",
                data={"amount": amount, "max_cex_order_amount": max_amt},
            )

    def validate_cex_access(self, *, exchange_id: str) -> None:
        ex = exchange_id.strip().lower()
        allow_exchanges = _parse_csv_set(os.getenv("ALLOW_EXCHANGES"))
        if allow_exchanges and ex not in allow_exchanges:
            raise PolicyError(
                code="exchange_not_allowed",
                message=f"Exchange '{exchange_id}' is not allowlisted.",
                data={"exchange": exchange_id, "allow_exchanges": sorted(allow_exchanges)},
            )


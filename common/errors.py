from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AppError(Exception):
    code: str
    message: str
    data: Dict[str, Any]

class MarketClosedError(AppError):
    def __init__(self, message: str = "Market is currently closed", data: Dict[str, Any] = None):
        super().__init__("market_closed", message, data or {})

class CircuitBreakerError(AppError):
    def __init__(self, message: str = "Circuit breaker triggered", data: Dict[str, Any] = None):
        super().__init__("circuit_breaker", message, data or {})


def classify_exception(e: Exception) -> AppError:
    """
    Map common brokerage / yfinance / network issues into stable error codes.
    """
    if isinstance(e, AppError):
        return e
        
    # General network / provider errors
    err_str = str(e).lower()
    
    if "rate limit" in err_str or "429" in err_str:
        return AppError("rate_limited", str(e), {})
    if "timeout" in err_str:
        return AppError("timeout", str(e), {})
    if "api key" in err_str or "unauthorized" in err_str or "forbidden" in err_str:
        return AppError("auth_error", str(e), {})
    if "not found" in err_str or "invalid symbol" in err_str:
        return AppError("bad_symbol", str(e), {})
    if "network" in err_str or "connection" in err_str:
        return AppError("network_error", str(e), {})

    return AppError("unknown_error", str(e), {})


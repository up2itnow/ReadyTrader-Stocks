from __future__ import annotations


def venue_allowed(execution_mode: str, venue: str) -> bool:
    """
    Router for stock execution.
    - stock/brokerage mode: only stock actions via brokerage
    """
    m = (execution_mode or "").strip().lower()
    v = (venue or "").strip().lower()

    if m == "stock" or m == "brokerage":
        return v in {"stock", "brokerage"}
    # Default to deny for safety
    return False


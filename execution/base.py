from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IBrokerage(ABC):
    """
    Interface for brokerage services.
    """
    @abstractmethod
    def is_available(self) -> bool:
        """Check if API keys are configured and service is ready."""
        pass

    @abstractmethod
    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "market", price: Optional[float] = None) -> Dict[str, Any]:
        """Place an order."""
        pass

    @abstractmethod
    def get_account_balance(self) -> Dict[str, float]:
        """Fetch account equity and cash."""
        pass

    @abstractmethod
    def list_positions(self) -> List[Dict[str, Any]]:
        """List all open positions."""
        pass

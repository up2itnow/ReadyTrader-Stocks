"""
Example plugin providers.

These are intentionally simple and offline-friendly so operators can test the plugin system without
adding new external dependencies.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class StaticJsonFileProvider:
    """
    Read ticker snapshots from a JSON file.

    File format:
    {
      "BTC/USDT": {"last": 50000, "bid": 49990, "ask": 50010, "timestamp_ms": 1730000000000, "source": "file"},
      "ETH/USDT": {"last": 2500}
    }
    """

    path: str
    provider_id: str = "file_feed"

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        sym = (symbol or "").strip().upper()
        p = Path(self.path)
        data = json.loads(p.read_text())
        if not isinstance(data, dict) or sym not in data:
            raise ValueError(f"No ticker for {sym} in {self.path}")
        t = data.get(sym) or {}
        if not isinstance(t, dict):
            raise ValueError(f"Invalid ticker shape for {sym}")
        now_ms = int(time.time() * 1000)
        return {
            "symbol": sym,
            "last": float(t.get("last") or 0.0),
            "bid": float(t["bid"]) if t.get("bid") is not None else None,
            "ask": float(t["ask"]) if t.get("ask") is not None else None,
            "timestamp_ms": int(t.get("timestamp_ms") or now_ms),
            "source": str(t.get("source") or "file"),
        }

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        raise ValueError("StaticJsonFileProvider does not provide OHLCV")

    def status(self) -> Dict[str, Any]:
        return {"provider_id": self.provider_id, "path": self.path}


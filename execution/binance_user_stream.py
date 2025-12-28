from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional

import requests
import websockets

from .cex_executor import load_cex_credentials


def _http_timeout() -> float:
    return float((os.getenv("HTTP_TIMEOUT_SEC") or "10").strip())


class BinanceUserStream:
    """
    Binance user data stream (optional private updates).

    This is best-effort and intentionally opt-in:
    - It is not started automatically (keeps CI deterministic)
    - It provides a lightweight way to observe order/execution updates without polling
    """

    def __init__(self, *, market_type: str = "spot", max_events: int = 500) -> None:
        self.market_type = (market_type or "spot").strip().lower()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None
        self._events: Deque[Dict[str, Any]] = deque(maxlen=max(50, int(max_events)))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def status(self) -> Dict[str, Any]:
        return {"running": bool(self._thread and self._thread.is_alive()), "last_error": self._last_error}

    def list_events(self, *, limit: int = 100) -> list[Dict[str, Any]]:
        n = max(0, int(limit))
        return list(self._events)[-n:]

    def _run(self) -> None:
        asyncio.run(self._run_async())

    def _create_listen_key(self) -> str:
        creds = load_cex_credentials("binance", require_auth=True)
        base = "https://api.binance.com"
        path = "/api/v3/userDataStream"
        if self.market_type in {"swap", "perp"}:
            base = "https://fapi.binance.com"
            path = "/fapi/v1/listenKey"
        url = base + path
        r = requests.post(url, headers={"X-MBX-APIKEY": creds.api_key}, timeout=_http_timeout())  # nosec B113
        r.raise_for_status()
        data = r.json()
        lk = str(data.get("listenKey") or "").strip()
        if not lk:
            raise ValueError("Binance did not return listenKey")
        return lk

    def _keepalive_listen_key(self, listen_key: str) -> None:
        creds = load_cex_credentials("binance", require_auth=True)
        base = "https://api.binance.com"
        path = "/api/v3/userDataStream"
        if self.market_type in {"swap", "perp"}:
            base = "https://fapi.binance.com"
            path = "/fapi/v1/listenKey"
        url = base + path
        r = requests.put(  # nosec B113
            url,
            headers={"X-MBX-APIKEY": creds.api_key},
            params={"listenKey": listen_key},
            timeout=_http_timeout(),
        )
        r.raise_for_status()

    def _ws_url(self, listen_key: str) -> str:
        if self.market_type in {"swap", "perp"}:
            return f"wss://fstream.binance.com/ws/{listen_key}"
        return f"wss://stream.binance.com:9443/ws/{listen_key}"

    async def _run_async(self) -> None:  # pragma: no cover (network loop)
        backoff = 1.0
        while not self._stop.is_set():
            try:
                listen_key = self._create_listen_key()
                last_keepalive = time.time()
                async with websockets.connect(self._ws_url(listen_key), ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    while not self._stop.is_set():
                        # Keepalive every ~30 minutes
                        if time.time() - last_keepalive > 25 * 60:
                            try:
                                self._keepalive_listen_key(listen_key)
                                last_keepalive = time.time()
                            except Exception as e:
                                self._last_error = f"keepalive_failed: {e}"

                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        event_type = str(msg.get("e") or msg.get("eventType") or "")
                        simplified = {
                            "market_type": self.market_type,
                            "event_type": event_type,
                            "event_time": msg.get("E"),
                            "symbol": msg.get("s"),
                            "order_id": msg.get("i"),
                            "client_order_id": msg.get("c"),
                            "order_status": msg.get("X"),
                            "exec_type": msg.get("x"),
                            "raw": msg,
                        }
                        self._events.append(simplified)
            except Exception as e:
                self._last_error = str(e)
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2)


class BinanceUserStreamManager:
    def __init__(self) -> None:
        self._spot = BinanceUserStream(market_type="spot")
        self._swap = BinanceUserStream(market_type="swap")

    def start(self, *, market_type: str) -> None:
        mt = (market_type or "spot").strip().lower()
        if mt in {"swap", "perp"}:
            self._swap.start()
            return
        self._spot.start()

    def stop(self, *, market_type: str) -> None:
        mt = (market_type or "spot").strip().lower()
        if mt in {"swap", "perp"}:
            self._swap.stop()
            return
        self._spot.stop()

    def list_events(self, *, market_type: str, limit: int = 100) -> list[Dict[str, Any]]:
        mt = (market_type or "spot").strip().lower()
        if mt in {"swap", "perp"}:
            return self._swap.list_events(limit=limit)
        return self._spot.list_events(limit=limit)

    def status(self) -> Dict[str, Any]:
        return {"spot": self._spot.status(), "swap": self._swap.status()}


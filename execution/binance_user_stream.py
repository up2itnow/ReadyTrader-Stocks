"""
Binance private user data streams (Phase 2.5).

This module implements an **opt-in** background websocket client for Binance user updates.
It is intentionally best-effort and lightweight:
- Not started automatically (keeps CI deterministic and avoids surprising network activity)
- Uses Binance's `listenKey` mechanism (created via REST, then consumed via websocket)
- Stores a simplified, non-sensitive subset of each event for operator visibility
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional

import requests
import websockets

from .cex_executor import load_cex_credentials


class _MetricsLike:
    def inc(self, name: str, value: int = 1) -> None:  # pragma: no cover
        raise NotImplementedError

    def set_gauge(self, name: str, value: float) -> None:  # pragma: no cover
        raise NotImplementedError


def _http_timeout() -> float:
    return float((os.getenv("HTTP_TIMEOUT_SEC") or "10").strip())


class BinanceUserStream:
    """
    Binance user data stream (optional private updates).

    This is best-effort and intentionally opt-in:
    - It is not started automatically (keeps CI deterministic)
    - It provides a lightweight way to observe order/execution updates without polling
    """

    def __init__(
        self,
        *,
        market_type: str = "spot",
        max_events: int = 500,
        metrics: _MetricsLike | None = None,
    ) -> None:
        self.market_type = (market_type or "spot").strip().lower()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None
        self._last_message_at: Optional[float] = None
        self._events: Deque[Dict[str, Any]] = deque(maxlen=max(50, int(max_events)))
        self._metrics = metrics
        self._metric_prefix = f"private_ws_binance_{self.market_type}"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if self._metrics:
            self._metrics.inc(f"{self._metric_prefix}_start_total", 1)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._metrics:
            self._metrics.inc(f"{self._metric_prefix}_stop_total", 1)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            age = None
            if self._last_message_at is not None:
                age = round(time.time() - self._last_message_at, 3)
            last_error = self._last_error
        if self._metrics and age is not None:
            self._metrics.set_gauge(f"{self._metric_prefix}_last_message_age_sec", float(age))
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "last_error": last_error,
            "last_message_age_sec": age,
        }

    def list_events(self, *, limit: int = 100) -> list[Dict[str, Any]]:
        n = max(0, int(limit))
        with self._lock:
            return list(self._events)[-n:]

    def _run(self) -> None:
        asyncio.run(self._run_async())

    def _create_listen_key(self) -> str:
        creds = load_cex_credentials("binance", require_auth=True)
        # Binance uses different hosts/paths for spot vs futures (swap/perp).
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
        # Listen keys expire unless kept alive periodically via REST.
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
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_connect_total", 1)
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
                                if self._metrics:
                                    self._metrics.inc(f"{self._metric_prefix}_keepalive_fail_total", 1)

                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        event_type = str(msg.get("e") or msg.get("eventType") or "")
                        # Keep a compact representation for quick debugging / operator inspection.
                        # We still include the raw message in case an operator needs full context.
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
                        with self._lock:
                            self._last_message_at = time.time()
                            self._events.append(simplified)
                        if self._metrics:
                            self._metrics.inc(f"{self._metric_prefix}_messages_total", 1)
            except Exception as e:
                with self._lock:
                    self._last_error = str(e)
                if self._metrics:
                    self._metrics.inc(f"{self._metric_prefix}_error_total", 1)
                # Jittered exponential backoff to avoid synchronized reconnect storms.
                jitter = 0.5 + (random.random() * 0.5)  # nosec B311 (non-crypto jitter)  # 0.5x .. 1.0x
                await asyncio.sleep(max(0.1, float(backoff)) * jitter)
                backoff = min(30.0, backoff * 2)


class BinanceUserStreamManager:
    def __init__(self, *, metrics: _MetricsLike | None = None) -> None:
        self._spot = BinanceUserStream(market_type="spot", metrics=metrics)
        self._swap = BinanceUserStream(market_type="swap", metrics=metrics)

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


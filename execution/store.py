"""
Two-step execution proposal store (Phase 6).

This is used when `EXECUTION_APPROVAL_MODE=approve_each`.
Instead of executing immediately, the server returns a proposal:
- `request_id`: lookup key
- `confirm_token`: single-use token (replay protection)
- `expires_at`: TTL deadline (prevents stale approvals)

Phase 1B: Optional SQLite persistence can be enabled for operator visibility.
Safety rules:
- Proposals are invalidated across restarts via a per-process session id (so stale approvals cannot execute).
- Risk consent is NOT persisted (consent remains in-memory only by design).
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Phase 2: Webhooks for notifications
try:
    from observability.webhooks import WebhookManager
except ImportError:
    WebhookManager = None


@dataclass
class ExecutionProposal:
    request_id: str
    confirm_token: str
    kind: str
    payload: Dict[str, Any]
    created_at: float
    expires_at: float
    confirmed_at: Optional[float] = None
    cancelled_at: Optional[float] = None


class ExecutionStore:
    """
    In-memory store for two-step execution proposals.
    Replay protection: proposal can be confirmed only once.
    """

    def __init__(self) -> None:
        # Accessed by MCP tool handlers; keep thread-safe (even if most workloads are single-threaded).
        self._lock = threading.Lock()
        self._items: Dict[str, ExecutionProposal] = {}
        self._conn: Optional[sqlite3.Connection] = None
        # Used to invalidate any persisted proposals across restarts.
        self._session_id = secrets.token_hex(8)

    def persistence_enabled(self) -> bool:
        return bool(self._db_path())

    def _db_path(self) -> str:
        default = "data/execution.db"
        p = (os.getenv("READYTRADER_EXECUTION_DB_PATH") or os.getenv("EXECUTION_DB_PATH") or default).strip()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def _get_conn(self) -> Optional[sqlite3.Connection]:
        path = self._db_path()
        if not path:
            return None
        if self._conn is not None:
            return self._conn
        # create lazily
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_proposals(
                request_id TEXT PRIMARY KEY,
                confirm_token TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                confirmed_at REAL,
                cancelled_at REAL,
                session_id TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        return self._conn

    def _persist(self, p: ExecutionProposal) -> None:
        """
        Persist a proposal best-effort (only if EXECUTION_DB_PATH is set).
        """
        conn = self._get_conn()
        if conn is None:
            return
        conn.execute(
            """
            INSERT INTO execution_proposals(
                request_id, confirm_token, kind, payload_json, created_at, expires_at,
                confirmed_at, cancelled_at, session_id
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
              confirmed_at=excluded.confirmed_at,
              cancelled_at=excluded.cancelled_at
            """,
            (
                p.request_id,
                p.confirm_token,
                p.kind,
                json.dumps(p.payload, sort_keys=True),
                float(p.created_at),
                float(p.expires_at),
                p.confirmed_at,
                p.cancelled_at,
                self._session_id,
            ),
        )
        conn.commit()

    def _load(self, request_id: str) -> Optional[ExecutionProposal]:
        """
        Load a proposal from SQLite if persistence is enabled.

        Only proposals created in the *current process session* are considered valid.
        """
        conn = self._get_conn()
        if conn is None:
            return None
        row = conn.execute(
            """
            SELECT
              request_id,
              confirm_token,
              kind,
              payload_json,
              created_at,
              expires_at,
              confirmed_at,
              cancelled_at,
              session_id
            FROM execution_proposals
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if not row:
            return None
        if row[8] != self._session_id:
            return None
        try:
            payload = json.loads(row[3]) if row[3] else {}
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        return ExecutionProposal(
            request_id=str(row[0]),
            confirm_token=str(row[1]),
            kind=str(row[2]),
            payload=payload,
            created_at=float(row[4]),
            expires_at=float(row[5]),
            confirmed_at=float(row[6]) if row[6] is not None else None,
            cancelled_at=float(row[7]) if row[7] is not None else None,
        )

    def create(self, *, kind: str, payload: Dict[str, Any], ttl_seconds: int = 120) -> ExecutionProposal:
        with self._lock:
            now = time.time()
            request_id = secrets.token_hex(12)
            confirm_token = secrets.token_hex(16)
            prop = ExecutionProposal(
                request_id=request_id,
                confirm_token=confirm_token,
                kind=kind,
                payload=payload,
                created_at=now,
                expires_at=now + ttl_seconds,
            )
            self._items[request_id] = prop
            self._persist(prop)
            
            # Phase 2: Notification callback
            if WebhookManager:
                # Attempt to extract symbol and amount for a prettier message
                amount = float(payload.get("amount") or 0.0)
                symbol = str(payload.get("symbol") or payload.get("from_token", "Unknown"))
                WebhookManager.notify_approval_required(
                    kind=kind,
                    amount=amount,
                    symbol=symbol,
                    request_id=request_id
                )
            
            return prop

    def get(self, request_id: str) -> Optional[ExecutionProposal]:
        with self._lock:
            p = self._items.get(request_id)
            if p is not None:
                return p
            p2 = self._load(request_id)
            if p2 is not None:
                self._items[request_id] = p2
            return p2

    def list_pending(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            pending = []
            for p in self._items.values():
                if p.cancelled_at or p.confirmed_at:
                    continue
                if p.expires_at <= now:
                    continue
                pending.append(
                    {
                        "request_id": p.request_id,
                        "kind": p.kind,
                        "created_at": p.created_at,
                        "expires_at": p.expires_at,
                    }
                )
            # Optionally merge persisted proposals (same-session only) that aren't loaded yet.
            conn = self._get_conn()
            if conn is not None:
                rows = conn.execute(
                    """
                    SELECT request_id, kind, created_at, expires_at
                    FROM execution_proposals
                    WHERE session_id = ? AND confirmed_at IS NULL AND cancelled_at IS NULL AND expires_at > ?
                    """,
                    (self._session_id, float(now)),
                ).fetchall()
                seen = {p["request_id"] for p in pending}
                for rid, kind, created_at, expires_at in rows:
                    if str(rid) in seen:
                        continue
                    pending.append(
                        {
                            "request_id": str(rid),
                            "kind": str(kind),
                            "created_at": float(created_at),
                            "expires_at": float(expires_at),
                        }
                    )
            return {"pending": pending}

    def cancel(self, request_id: str) -> bool:
        with self._lock:
            p = self._items.get(request_id) or self._load(request_id)
            if not p:
                return False
            if p.confirmed_at is not None:
                return False
            if p.cancelled_at is not None:
                return False
            p.cancelled_at = time.time()
            self._items[request_id] = p
            self._persist(p)
            return True

    def confirm(self, request_id: str, confirm_token: str) -> ExecutionProposal:
        with self._lock:
            p = self._items.get(request_id) or self._load(request_id)
            if not p:
                raise ValueError("Unknown request_id")
            now = time.time()
            if p.expires_at <= now:
                raise ValueError("Proposal expired")
            if p.cancelled_at is not None:
                raise ValueError("Proposal cancelled")
            if p.confirmed_at is not None:
                raise ValueError("Proposal already confirmed")
            if secrets.compare_digest(p.confirm_token, confirm_token) is False:
                raise ValueError("Invalid confirm_token")
            p.confirmed_at = now
            self._items[request_id] = p
            self._persist(p)
            return p


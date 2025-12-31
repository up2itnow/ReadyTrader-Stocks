import pytest
import sqlite3
import os
import json
from unittest.mock import patch, MagicMock
from observability.audit import AuditLog

@pytest.fixture
def audit_db(tmp_path):
    db_path = str(tmp_path / "audit" / "test_audit.db")
    with patch.dict(os.environ, {"AUDIT_DB_PATH": db_path}):
        log = AuditLog()
        yield log

def test_audit_logs_and_verifies(audit_db):
    assert audit_db.enabled()
    
    audit_db.append(ts_ms=1000, request_id="req1", tool="test_tool", ok=True, summary={"a": 1})
    audit_db.append(ts_ms=2000, request_id="req2", tool="test_tool", ok=False, summary={"a": 2})
    
    assert audit_db.verify_integrity()
    
    # Manually tamper with DB
    conn = sqlite3.connect(audit_db._db_path())
    conn.execute("UPDATE audit_events SET tool='tampered' WHERE request_id='req1'")
    conn.commit()
    conn.close()
    
    assert not audit_db.verify_integrity()

def test_export_tax_report(audit_db):
    audit_db.append(ts_ms=1000, request_id="r1", tool="swap_tokens", ok=True, summary={"from_token": "USDC", "to_token": "ETH", "amount": 100})
    audit_db.append(ts_ms=2000, request_id="r2", tool="place_cex_order", ok=True, summary={"symbol": "AAPL", "side": "buy", "amount": 10})
    audit_db.append(ts_ms=3000, request_id="r3", tool="transfer_eth", ok=True, summary={"chain": "ETH", "amount": 1})
    
    csv_out = audit_db.export_tax_report()
    assert "USDC -> ETH" in csv_out
    assert "AAPL" in csv_out
    assert "SEND" in csv_out

def test_audit_disabled_if_no_path():
    with patch.dict(os.environ, {}, clear=True):
        # Default is 'data/audit.db', so it might be enabled if folder exists.
        # Patch makedirs to fail or patch path to empty
        with patch("observability.audit.os.makedirs", side_effect=OSError):
             with patch("observability.audit.os.path.exists", return_value=False):
                 log = AuditLog()
                 # If _db_path catches OSError and returns ""
                 assert not log.enabled()
                 log.append(ts_ms=1, request_id="r", tool="t", ok=True) # Should just return

def test_initial_migration(tmp_path):
    # Test that migration adds columns if missing
    db_path = str(tmp_path / "old_audit.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE audit_events(id INTEGER PRIMARY KEY, ts_ms INT, request_id TEXT, tool TEXT, ok INT, error_code TEXT, mode TEXT, venue TEXT, exchange TEXT, market_type TEXT, summary_json TEXT)")
    conn.commit()
    conn.close()
    
    with patch.dict(os.environ, {"AUDIT_DB_PATH": db_path}):
        log = AuditLog()
        log.append(ts_ms=1000, request_id="req1", tool="test", ok=True) # Triggers migration
        
        # Verify columns exist
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(audit_events)")
        columns = [r[1] for r in cursor.fetchall()]
        assert "hash" in columns
        assert "previous_hash" in columns

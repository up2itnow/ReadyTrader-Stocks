import os

from observability.audit import AuditLog


def test_audit_hashing_integrity():
    db_path = "data/test_audit.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    os.environ["AUDIT_DB_PATH"] = db_path
    audit = AuditLog()
    
    # 1. Append multiple events
    audit.append(ts_ms=1000, request_id="req1", tool="get_stock_price", ok=True, summary={"symbol": "AAPL"})
    audit.append(ts_ms=2000, request_id="req2", tool="place_market_order", ok=True, summary={"symbol": "AAPL", "side": "buy"})
    audit.append(ts_ms=3000, request_id="req3", tool="get_market_sentiment", ok=False, error_code="timeout")
    
    # 2. Use the built-in integrity check
    is_ok = audit.verify_integrity()
    assert is_ok, "Audit log integrity check failed!"
    
    print("Audit Hashing Integrity Verified via verify_integrity()!")

if __name__ == "__main__":
    test_audit_hashing_integrity()

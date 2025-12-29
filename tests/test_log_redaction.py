from observability.logging import redact


def test_redact_removes_sensitive_keys():
    inp = {
        "api_key": "abc",
        "nested": {"password": "p", "ok": 1},
        "tokenValue": "t",
        "safe": "x",
    }
    out = redact(inp)
    assert out["api_key"] == "***REDACTED***"
    assert out["nested"]["password"] == "***REDACTED***"
    assert out["tokenValue"] == "***REDACTED***"
    assert out["safe"] == "x"


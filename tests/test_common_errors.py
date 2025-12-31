import pytest
from common.errors import AppError, MarketClosedError, CircuitBreakerError, classify_exception

def test_app_error_basics():
    e = AppError("code", "msg", {"a": 1})
    assert e.code == "code"
    assert e.message == "msg"
    assert e.data["a"] == 1

def test_special_errors():
    e = MarketClosedError()
    assert e.code == "market_closed"
    
    e2 = CircuitBreakerError("boom")
    assert e2.code == "circuit_breaker"
    assert e2.message == "boom"

def test_classify_exception():
    e = AppError("c", "m", {})
    assert classify_exception(e) is e
    
    assert classify_exception(Exception("Rate limit 429")).code == "rate_limited"
    assert classify_exception(Exception("Connection timeout")).code == "timeout"
    assert classify_exception(Exception("Invalid API key")).code == "auth_error"
    assert classify_exception(Exception("Symbol not found")).code == "bad_symbol"
    assert classify_exception(Exception("Network error")).code == "network_error"
    assert classify_exception(Exception("Whoops")).code == "unknown_error"

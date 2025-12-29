import ccxt
import pytest

from execution.retry import with_retry


def test_with_retry_retries_transient_and_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ccxt.NetworkError("temporary")
        return "ok"

    # avoid real sleep in test
    monkeypatch.setattr("execution.retry.time.sleep", lambda _: None)
    monkeypatch.setenv("CEX_RETRY_MAX_ATTEMPTS", "3")
    out = with_retry("op", fn)
    assert out == "ok"
    assert calls["n"] == 2


def test_with_retry_does_not_retry_non_transient(monkeypatch):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ccxt.AuthenticationError("bad key")

    monkeypatch.setattr("execution.retry.time.sleep", lambda _: None)
    monkeypatch.setenv("CEX_RETRY_MAX_ATTEMPTS", "3")
    with pytest.raises(Exception) as e:
        with_retry("op", fn)
    assert "ccxt_auth_error" in str(e.value)
    assert calls["n"] == 1


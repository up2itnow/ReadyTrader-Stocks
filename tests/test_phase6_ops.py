import json
from unittest.mock import MagicMock, patch

import server
from rate_limiter import FixedWindowRateLimiter


def test_rate_limiting_blocks_after_limit():
    # Reset limiter for deterministic test
    server.rate_limiter = FixedWindowRateLimiter()
    with patch.dict("os.environ", {"RATE_LIMIT_GET_NEWS_PER_MIN": "1"}):
        a = json.loads(server._tool_get_news())
        assert a["ok"] is True
        b = json.loads(server._tool_get_news())
        assert b["ok"] is False
        assert b["error"]["code"] == "rate_limited"


def test_advanced_overrides_require_consent():
    server.ADV_DISCLOSURE_ACCEPTED = False
    res = json.loads(server._tool_set_policy_overrides('{"MAX_TRADE_AMOUNT": 999}'))
    assert res["ok"] is False
    assert res["error"]["code"] == "advanced_consent_required"


def test_risk_profile_aggressive_requires_advanced_consent():
    server.ADV_DISCLOSURE_ACCEPTED = False
    res = json.loads(server._tool_set_execution_preferences("auto", risk_profile="aggressive"))
    assert res["ok"] is False


def test_two_step_confirmation_for_cex_order():
    # Configure live mode gating to allow confirm flow
    with patch.dict(
        "os.environ",
        {
            "EXECUTION_MODE": "cex",
            "PAPER_MODE": "false",
            "LIVE_TRADING_ENABLED": "true",
            "TRADING_HALTED": "false",
            "HUMAN_CONFIRMATION": "true",
        },
    ):
        # Force global flags (module-level) for test
        server.PAPER_MODE = False
        server.DISCLOSURE_ACCEPTED = True
        server.EXECUTION_APPROVAL_MODE = "approve_each"
        server.rate_limiter = FixedWindowRateLimiter()

        # Stub out ccxt executor
        fake_executor = MagicMock()
        fake_executor.place_order.return_value = {"id": "order123", "status": "open"}
        fake_executor.normalize_order.return_value = {"id": "order123", "status": "open"}
        with patch("server.CexExecutor", return_value=fake_executor):
            proposal = json.loads(server._tool_place_cex_order("BTC/USDT", "buy", 0.01, exchange="binance"))
            assert proposal["ok"] is True
            data = proposal["data"]
            assert data["needs_confirmation"] is True
            request_id = data["request_id"]
            confirm_token = data["confirm_token"]

            confirmed = json.loads(server._tool_confirm_execution(request_id, confirm_token))
            assert confirmed["ok"] is True
            assert confirmed["data"]["kind"] == "place_cex_order"


def test_cex_order_auto_executes_when_approval_mode_auto():
    with patch.dict(
        "os.environ",
        {
            "EXECUTION_MODE": "cex",
            "PAPER_MODE": "false",
            "LIVE_TRADING_ENABLED": "true",
            "TRADING_HALTED": "false",
        },
    ):
        server.PAPER_MODE = False
        server.DISCLOSURE_ACCEPTED = True
        server.EXECUTION_APPROVAL_MODE = "auto"
        server.rate_limiter = FixedWindowRateLimiter()

        fake_executor = MagicMock()
        fake_executor.place_order.return_value = {"id": "order999", "status": "open"}
        fake_executor.normalize_order.return_value = {"id": "order999", "status": "open"}
        with patch("server.CexExecutor", return_value=fake_executor):
            res = json.loads(
                server._tool_place_cex_order(
                    "BTC/USDT",
                    "buy",
                    0.01,
                    exchange="binance",
                    idempotency_key="k1",
                )
            )
            assert res["ok"] is True
            assert res["data"]["venue"] == "cex"
            assert "order" in res["data"]

            # Second call with same idempotency key should be reused
            res2 = json.loads(
                server._tool_place_cex_order(
                    "BTC/USDT",
                    "buy",
                    0.01,
                    exchange="binance",
                    idempotency_key="k1",
                )
            )
            assert res2["ok"] is True
            assert res2["data"].get("reused") is True


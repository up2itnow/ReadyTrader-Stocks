import json
from unittest.mock import patch

import server


def test_start_private_ws_blocked_in_paper_mode():
    with patch("server.PAPER_MODE", True):
        res = json.loads(server._tool_start_cex_private_ws(exchange="binance", market_type="spot"))
        assert res["ok"] is False
        assert res["error"]["code"] == "paper_mode_not_supported"


def test_private_ws_rejects_unknown_exchange():
    with patch("server.PAPER_MODE", False):
        res = json.loads(server._tool_start_cex_private_ws(exchange="kraken", market_type="spot"))
        assert res["ok"] is False
        assert res["error"]["code"] == "unsupported_exchange"


from unittest.mock import patch

from execution.cex_executor import CexExecutor


class FakeExchange:
    def __init__(self, markets):
        self._markets = markets
        self.id = "binance"
        self.has = {"createOrder": True, "fetchBalance": True}
        self.timeframes = {"1m": "1m"}

    def load_markets(self):
        return self._markets

    def create_order(self, symbol, order_type, side, amount, price, params):
        return {
            "id": "order1",
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "status": "open",
            "amount": amount,
            "price": price,
            "clientOrderId": params.get("clientOrderId") if params else None,
        }


def test_resolve_symbol_swap_prefers_swap_market():
    markets = {
        "BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "spot": True},
        "BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT", "base": "BTC", "quote": "USDT", "swap": True},
    }
    fake = FakeExchange(markets)
    with patch("execution.cex_executor._get_private_exchange", return_value=fake):
        ex = CexExecutor("binance", market_type="swap", auth=True)
        assert ex.resolve_symbol("btc/usdt") == "BTC/USDT:USDT"


def test_place_order_uses_resolved_symbol_and_params():
    markets = {
        "BTC/USDT:USDT": {"symbol": "BTC/USDT:USDT", "base": "BTC", "quote": "USDT", "swap": True},
    }
    fake = FakeExchange(markets)
    with patch("execution.cex_executor._get_private_exchange", return_value=fake):
        ex = CexExecutor("binance", market_type="perp", auth=True)
        order = ex.place_order(
            symbol="BTC/USDT",
            side="buy",
            amount=0.01,
            order_type="market",
            params={"clientOrderId": "cid-1"},
        )
        assert order["symbol"] == "BTC/USDT:USDT"
        assert order["clientOrderId"] == "cid-1"


def test_get_capabilities_works_without_auth():
    markets = {
        "BTC/USDT": {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "spot": True},
    }
    fake = FakeExchange(markets)
    with patch("execution.cex_executor._get_public_exchange", return_value=fake):
        ex = CexExecutor("binance", market_type="spot", auth=False)
        cap = ex.get_capabilities(symbol="BTC/USDT")
        assert cap["exchange_id"] == "binance"
        assert cap["market_type"] == "spot"
        assert cap["resolved_symbol"] == "BTC/USDT"


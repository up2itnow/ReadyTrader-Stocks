import os
import pytest
from unittest.mock import MagicMock, patch
from execution.alpaca_service import AlpacaBrokerage

@patch("alpaca_trade_api.REST")
def test_alpaca_brokerage_init(mock_rest):
    with patch.dict(os.environ, {"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"}):
        brokerage = AlpacaBrokerage()
        assert brokerage.is_available() is True
        mock_rest.assert_called_once()

@patch("alpaca_trade_api.REST")
def test_alpaca_brokerage_place_order(mock_rest):
    with patch.dict(os.environ, {"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"}):
        mock_api = MagicMock()
        mock_order = MagicMock()
        mock_order.id = "alpaca_1"
        mock_order.status = "open"
        mock_order.symbol = "AAPL"
        mock_order.side = "buy"
        mock_order.qty = "5"
        mock_order.client_order_id = "abc"
        mock_order.type = "market"
        mock_api.submit_order.return_value = mock_order
        mock_rest.return_value = mock_api
        
        brokerage = AlpacaBrokerage()
        res = brokerage.place_order(symbol="AAPL", side="buy", qty=5)
        
        assert res["id"] == "alpaca_1"
        assert res["symbol"] == "AAPL"
        assert res["qty"] == 5.0
        mock_api.submit_order.assert_called_once()

@patch("alpaca_trade_api.REST")
def test_alpaca_brokerage_get_balance(mock_rest):
    with patch.dict(os.environ, {"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"}):
        mock_api = MagicMock()
        mock_account = MagicMock()
        mock_account.equity = "100000.0"
        mock_account.cash = "50000.0"
        mock_account.buying_power = "200000.0"
        mock_api.get_account.return_value = mock_account
        mock_rest.return_value = mock_api
        
        brokerage = AlpacaBrokerage()
        res = brokerage.get_account_balance()
        
        assert res["equity"] == 100000.0
        assert res["cash"] == 50000.0

import pytest
from unittest.mock import patch
from execution.retail_services import SchwabBrokerage, EtradeBrokerage, RobinhoodBrokerage

def test_schwab_brokerage():
    # Not Configured
    with patch.dict("os.environ", {}, clear=True):
        schwab = SchwabBrokerage()
        assert not schwab.is_available()
        
        with pytest.raises(RuntimeError):
            schwab.place_order("AAPL", "buy", 10)
            
        with pytest.raises(RuntimeError):
            schwab.get_account_balance()
            
    # Configured (Placeholder)
    with patch.dict("os.environ", {"SCHWAB_APP_KEY": "k", "SCHWAB_APP_SECRET": "s"}):
        schwab = SchwabBrokerage()
        assert schwab.is_available()
        
        res = schwab.place_order("AAPL", "buy", 10)
        assert res["status"] == "error"
        assert "pending" in res["message"]
        
        bal = schwab.get_account_balance()
        assert bal["equity"] == 0.0

def test_etrade_brokerage():
    with patch.dict("os.environ", {}, clear=True):
         et = EtradeBrokerage()
         assert not et.is_available()
    
    with patch.dict("os.environ", {"ETRADE_KEY": "k"}):
         et = EtradeBrokerage()
         assert et.is_available()
         assert et.get_account_balance()["equity"] == 0.0
         assert et.list_positions() == []

def test_robinhood_brokerage():
    with patch.dict("os.environ", {}, clear=True):
         rh = RobinhoodBrokerage()
         assert not rh.is_available()
         
    with patch.dict("os.environ", {"ROBINHOOD_USER": "u"}):
         rh = RobinhoodBrokerage()
         assert rh.is_available()

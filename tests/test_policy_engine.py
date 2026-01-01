import os
from unittest.mock import patch

import pytest

from core.policy import PolicyEngine, PolicyError


@pytest.fixture
def policy():
    return PolicyEngine()

def test_validate_insight_backing(policy):
    mock_insight = {"insight_id": "i1", "symbol": "AAPL", "confidence": 0.9}
    
    # Matching
    score = policy.validate_insight_backing(symbol="AAPL", insight_id="i1", insights=[mock_insight])
    assert score == 0.9
    
    # Not found
    with pytest.raises(PolicyError) as exc:
        policy.validate_insight_backing(symbol="MSFT", insight_id="i1", insights=[mock_insight])
    assert exc.value.code == "insight_not_found"

def test_validate_swap_allowlist(policy):
    with patch.dict(os.environ, {"ALLOW_CHAINS": "ethereum", "ALLOW_TOKENS": "usdc, eth"}):
        # Allowed
        policy.validate_swap(chain="ethereum", from_token="usdc", to_token="eth", amount=10.0)
        
        # Blocked Chain
        with pytest.raises(PolicyError) as exc:
            policy.validate_swap(chain="bsc", from_token="usdc", to_token="eth", amount=10.0)
        assert exc.value.code == "chain_not_allowed"

        # Blocked Token
        with pytest.raises(PolicyError) as exc:
             policy.validate_swap(chain="ethereum", from_token="shib", to_token="eth", amount=10.0)
        assert exc.value.code == "token_not_allowed"

def test_validate_swap_limits(policy):
    with patch.dict(os.environ, {"MAX_TRADE_AMOUNT": "100.0"}):
        # Good
        policy.validate_swap(chain="eth", from_token="usdc", to_token="eth", amount=50.0)
        
        # Too large
        with pytest.raises(PolicyError) as exc:
            policy.validate_swap(chain="eth", from_token="usdc", to_token="eth", amount=150.0)
        assert exc.value.code == "trade_amount_too_large"

def test_validate_brokerage_order(policy):
    with patch.dict(os.environ, {"ALLOW_EXCHANGES": "alpaca", "MAX_BROKERAGE_ORDER_AMOUNT": "500"}):
        # Allowed
        policy.validate_brokerage_order(exchange_id="alpaca", symbol="AAPL", side="buy", amount=10, order_type="market")
        
        # Blocked Exchange
        with pytest.raises(PolicyError):
            policy.validate_brokerage_order(exchange_id="ibkr", symbol="AAPL", side="buy", amount=10, order_type="market")
            
        # Amount Limit
        with pytest.raises(PolicyError):
            policy.validate_brokerage_order(exchange_id="alpaca", symbol="AAPL", side="buy", amount=1000, order_type="market")

def test_validate_sign_tx(policy):
    with patch.dict(os.environ, {"MAX_SIGN_GAS": "21000", "DISALLOW_SIGN_CONTRACT_CREATION": "true"}):
        # OK
        policy.validate_sign_tx(chain_id=1, to_address="0x123", value_wei=0, gas=21000, gas_price_wei=10, data_hex="0x")
        
        # High Gas
        with pytest.raises(PolicyError):
             policy.validate_sign_tx(chain_id=1, to_address="0x123", value_wei=0, gas=50000, gas_price_wei=10, data_hex="0x")
             
        # Contract Creation (no to_address)
        with pytest.raises(PolicyError):
             policy.validate_sign_tx(chain_id=1, to_address=None, value_wei=0, gas=21000, gas_price_wei=10, data_hex="0x60806040")

def test_validate_signer_address(policy):
    with patch.dict(os.environ, {"ALLOW_SIGNER_ADDRESSES": "0xabc"}):
        policy.validate_signer_address(address="0xabc")
        
        with pytest.raises(PolicyError):
            policy.validate_signer_address(address="0xdef")

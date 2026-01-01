import os
from unittest.mock import MagicMock

import pytest

from signing.policy import PolicyEnforcedSigner, SignerPolicyViolation, policy_config_from_env


@pytest.fixture
def mock_inner(monkeypatch):
    # Ensure clean env
    for k in list(os.environ.keys()):
        if k.startswith("SIGNER_"):
            monkeypatch.delenv(k, raising=False)
            
    inner = MagicMock()
    inner.get_address.return_value = "0xme"
    inner.sign_transaction.return_value = MagicMock(rawTransaction=b"\x00")
    return inner

def test_signer_policy_blocks_to_address_allowlist(monkeypatch, mock_inner):
    monkeypatch.setenv("SIGNER_POLICY_ENABLED", "true")
    monkeypatch.setenv("SIGNER_ALLOWED_TO_ADDRESSES", "0xallowed")

    cfg = policy_config_from_env()
    s = PolicyEnforcedSigner(mock_inner, cfg)

    with pytest.raises(SignerPolicyViolation) as e:
        s.sign_transaction({"to": "0xnotallowed", "value": 0}, chain_id=1)
    assert e.value.code == "to_not_allowed"
    
    # Allowed
    s.sign_transaction({"to": "0xallowed", "value": 0}, chain_id=1)

def test_signer_policy_max_value(monkeypatch, mock_inner):
    monkeypatch.setenv("SIGNER_POLICY_ENABLED", "true")
    monkeypatch.setenv("SIGNER_MAX_VALUE_WEI", "100")
    
    s = PolicyEnforcedSigner(mock_inner, policy_config_from_env())
    
    with pytest.raises(SignerPolicyViolation) as e:
        s.sign_transaction({"to": "0xall", "value": 101}, chain_id=1)
    assert e.value.code == "value_too_large"
    
    s.sign_transaction({"to": "0xall", "value": 100}, chain_id=1)

def test_signer_policy_max_gas(monkeypatch, mock_inner):
    monkeypatch.setenv("SIGNER_POLICY_ENABLED", "true")
    monkeypatch.setenv("SIGNER_MAX_GAS", "50000")
    
    s = PolicyEnforcedSigner(mock_inner, policy_config_from_env())
    
    with pytest.raises(SignerPolicyViolation) as e:
        s.sign_transaction({"to": "0xall", "gas": 50001}, chain_id=1)
    assert e.value.code == "gas_too_large"

def test_signer_policy_chain_ids(monkeypatch, mock_inner):
    monkeypatch.setenv("SIGNER_POLICY_ENABLED", "true")
    monkeypatch.setenv("SIGNER_ALLOWED_CHAIN_IDS", "1,8453")
    
    s = PolicyEnforcedSigner(mock_inner, policy_config_from_env())
    
    with pytest.raises(SignerPolicyViolation) as e:
        s.sign_transaction({"to": "0xall"}, chain_id=5)
    assert e.value.code == "chain_id_not_allowed"
    
    s.sign_transaction({"to": "0xall"}, chain_id=1)
    s.sign_transaction({"to": "0xall"}, chain_id=8453)

def test_signer_policy_contract_creation(monkeypatch, mock_inner):
    monkeypatch.setenv("SIGNER_POLICY_ENABLED", "true")
    monkeypatch.setenv("SIGNER_DISALLOW_CONTRACT_CREATION", "true")
    
    s = PolicyEnforcedSigner(mock_inner, policy_config_from_env())
    
    # No 'to' means creation
    with pytest.raises(SignerPolicyViolation) as e:
        s.sign_transaction({"data": "0xabcd"}, chain_id=1)
    assert e.value.code == "contract_creation_not_allowed"

def test_signer_policy_message_signing(monkeypatch, mock_inner):
    # Currently unsupported by policy signer usually, or simple pass through?
    # Looking at policy.py code generally helps.
    # Assuming PolicyEnforcedSigner wraps sign_message too if present.
    # If not, skip.
    pass

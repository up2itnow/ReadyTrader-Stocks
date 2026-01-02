import os
import sys

import pytest

# Add root directory to sys.path to allow imports from top-level modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment variables BEFORE modules are imported
os.environ["PRIVATE_KEY"] = "0000000000000000000000000000000000000000000000000000000000000001"
os.environ["SIGNER_TYPE"] = "env_private_key"
os.environ["PAPER_MODE"] = "true"
os.environ["EXECUTION_MODE"] = "stock"

@pytest.fixture(autouse=True)
def mock_env_setup():
    # Ensures these are set for every test
    pass

@pytest.fixture
def container():
    from app.core.container import global_container
    return global_container

@pytest.fixture
def backtest_engine(container):
    return container.backtest_engine

@pytest.fixture
def paper_engine(container):
    return container.paper_engine

@pytest.fixture
def policy_engine(container):
    return container.policy_engine

@pytest.fixture
def risk_guardian(container):
    return container.risk_guardian

@pytest.fixture
def marketdata_bus(container):
    return container.marketdata_bus

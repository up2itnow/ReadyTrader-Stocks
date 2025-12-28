"""
ReadyTrader MCP server.

This module is intentionally the “thin integration layer” that exposes MCP tools to AI agents.
Core responsibilities:
- Route requests to the appropriate subsystem (paper trading, CEX, DEX, backtest, synthetic stress).
- Enforce safety gates for LIVE execution (kill switch, one-time risk disclosure, optional per-trade approval).
- Apply centralized policy checks (allowlists/limits) and optional advanced overrides (with extra consent).
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from web3 import Web3

from backtest_engine import BacktestEngine
from dex_handler import DexHandler
from exchange_provider import ExchangeProvider
from execution.cex_executor import CexExecutor
from execution.router import venue_allowed
from execution_store import ExecutionStore
from intelligence import (
    analyze_social_sentiment,
    fetch_financial_news,
    get_cached_sentiment_score,
    get_fear_greed_index,
    get_market_news,
)
from learning import Learner
from market_regime import RegimeDetector
from paper_engine import PaperTradingEngine
from policy_engine import PolicyEngine, PolicyError
from rate_limiter import FixedWindowRateLimiter, RateLimitError
from recommendations import recommend_settings as _recommend_settings
from risk_manager import RiskGuardian
from signing import get_signer
from stress_test_engine import run_synthetic_stress_test as _run_synth_stress

load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("ReadyTrader")

# Configuration
PAPER_MODE = os.getenv("PAPER_MODE", "true").lower() == "true"
paper_engine = PaperTradingEngine() if PAPER_MODE else None
backtest_engine = BacktestEngine()
regime_detector = RegimeDetector()
risk_guardian = RiskGuardian()
exchange_provider = ExchangeProvider()
dex_handler = DexHandler()
learner = Learner()

# Phase 1: Central policy engine (always-on for live execution)
policy_engine = PolicyEngine()
rate_limiter = FixedWindowRateLimiter()
execution_store = ExecutionStore()

# Phase B: idempotency store (per-process, non-persistent)
IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}

# Phase 1: Per-process (non-persistent) live trading consent gate
DISCLOSURE_VERSION = "1"
DISCLOSURE_ACCEPTED = False
DISCLOSURE_ACCEPTED_AT: Optional[str] = None
DISCLOSURE_TEXT = (
    "Live Trading Risk Disclosure (Consent Required)\n"
    "Trading digital assets involves substantial risk. You may lose some or all funds you use. "
    "Markets can be highly volatile; losses can occur rapidly due to price movements, slippage, fees, "
    "liquidity constraints, network conditions, software errors, or third-party outages.\n\n"
    "This software may place trades automatically. You are solely responsible for supervision, configuration "
    "of safety limits, and securing keys/credentials.\n\n"
    "By selecting “I Accept”, you acknowledge you understand these risks and agree to use this software at your own "
    "risk.\n"
    "This is not financial, investment, legal, or tax advice."
)

# Phase 6: Advanced risk mode (per-process, non-persistent) consent
ADV_DISCLOSURE_VERSION = "1"
ADV_DISCLOSURE_ACCEPTED = False
ADV_DISCLOSURE_ACCEPTED_AT: Optional[str] = None
ADV_DISCLOSURE_TEXT = (
    "Advanced Risk Mode Disclosure (Urgent – Consent Required)\n"
    "You are enabling elevated risk controls that can increase position sizing and loosen safety limits.\n"
    "This can materially increase the probability and magnitude of losses, including total loss of funds.\n\n"
    "By accepting, you acknowledge you understand this mode increases risk beyond default safeguards and you accept "
    "full responsibility.\n"
    "This is not financial, investment, legal, or tax advice."
)

# Phase 6: In-memory policy overrides (reset on restart). Used only if advanced consent is accepted.
POLICY_OVERRIDES: Dict[str, Any] = {}
RISK_PROFILE: str = os.getenv("RISK_PROFILE", "conservative").strip().lower()

# Phase 6: Execution approval mode (per-process, non-persistent)
# - "auto": execute immediately (default)
# - "approve_each": return a proposal + require confirm_execution
_env_approval_mode = os.getenv("EXECUTION_APPROVAL_MODE", "").strip().lower()
if not _env_approval_mode:
    # Backward compat: HUMAN_CONFIRMATION=true implies approve_each
    _env_human = os.getenv("HUMAN_CONFIRMATION", "false").strip().lower() == "true"
    _env_approval_mode = "approve_each" if _env_human else "auto"
EXECUTION_APPROVAL_MODE = _env_approval_mode if _env_approval_mode in {"auto", "approve_each"} else "auto"

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _json_ok(data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": True, "data": data or {}}
    return json.dumps(payload, indent=2, sort_keys=True)

def _json_err(code: str, message: str, data: Dict[str, Any] | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message, "data": data or {}}}
    return json.dumps(payload, indent=2, sort_keys=True)

def _get_execution_mode() -> str:
    return os.getenv("EXECUTION_MODE", "dex").strip().lower()

def _is_live_trading_enabled() -> bool:
    return os.getenv("LIVE_TRADING_ENABLED", "false").strip().lower() == "true"

def _is_trading_halted() -> bool:
    return os.getenv("TRADING_HALTED", "false").strip().lower() == "true"

def _require_live_execution_allowed(action: str) -> Optional[str]:
    """
    Phase 1 safety: for any live execution action, enforce:
    - kill switch
    - LIVE_TRADING_ENABLED (explicit opt-in)
    - per-process risk disclosure consent
    """
    global DISCLOSURE_ACCEPTED
    if PAPER_MODE:
        return None
    if _is_trading_halted():
        return _json_err(
            "trading_halted",
            "Live trading is currently halted (TRADING_HALTED=true).",
            {"action": action},
        )
    if not _is_live_trading_enabled():
        return _json_err(
            "live_trading_disabled",
            "Live trading is disabled. Set LIVE_TRADING_ENABLED=true to allow live execution.",
            {"action": action},
        )
    if not DISCLOSURE_ACCEPTED:
        return _json_err(
            "consent_required",
            (
                "Live trading requires risk disclosure consent. Call get_risk_disclosure(), then "
                "accept_risk_disclosure(true)."
            ),
            {"action": action, "disclosure_version": DISCLOSURE_VERSION},
        )
    return None

def _rate_limit(tool_name: str) -> Optional[str]:
    """
    Phase 6: rate limiting per tool (in-memory).

    Env:
      - RATE_LIMIT_DEFAULT_PER_MIN (int, default 120)
      - RATE_LIMIT_EXECUTION_PER_MIN (int, default 20)
      - RATE_LIMIT_<TOOLNAME>_PER_MIN (int) overrides specific tools
    """
    tool_key = tool_name.strip().lower()
    per_min_key = f"RATE_LIMIT_{tool_key.upper()}_PER_MIN"
    default_per_min = int(os.getenv("RATE_LIMIT_DEFAULT_PER_MIN", "120"))
    exec_per_min = int(os.getenv("RATE_LIMIT_EXECUTION_PER_MIN", "20"))
    limit = int(os.getenv(per_min_key, str(default_per_min)))

    # tighter defaults for execution tools
    if tool_key in {"swap_tokens", "transfer_eth", "place_cex_order"}:
        limit = int(os.getenv(per_min_key, str(exec_per_min)))

    try:
        rate_limiter.check(key=f"tool:{tool_key}", limit=limit, window_seconds=60)
        return None
    except RateLimitError as e:
        return _json_err(e.code, e.message, e.data)

def _policy_override_value(key: str, default: Any) -> Any:
    return POLICY_OVERRIDES.get(key, default)

def _advanced_mode_allowed() -> bool:
    return ADV_DISCLOSURE_ACCEPTED is True

def _effective_overrides() -> Dict[str, float]:
    # Only apply overrides if Advanced Risk consent is accepted.
    if not _advanced_mode_allowed():
        return {}
    # Normalize values to floats; ignore invalid entries.
    def _to_float(x: Any) -> float | None:
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    out: Dict[str, float] = {}
    for k, v in POLICY_OVERRIDES.items():
        fv = _to_float(v)
        if fv is None:
            continue
        out[k] = fv
    return out

def _human_confirmation_enabled() -> bool:
    return EXECUTION_APPROVAL_MODE == "approve_each"

def _get_execution_approval_mode() -> str:
    return EXECUTION_APPROVAL_MODE

def _set_execution_approval_mode(mode: str) -> None:
    global EXECUTION_APPROVAL_MODE
    m = (mode or "").strip().lower()
    if m not in {"auto", "approve_each"}:
        raise ValueError("mode must be 'auto' or 'approve_each'")
    EXECUTION_APPROVAL_MODE = m

def _set_risk_profile(profile: str) -> None:
    global RISK_PROFILE, POLICY_OVERRIDES
    p = (profile or "").strip().lower()
    if p not in {"conservative", "balanced", "aggressive"}:
        raise ValueError("profile must be conservative, balanced, or aggressive")
    # Aggressive requires advanced consent
    if p == "aggressive" and not _advanced_mode_allowed():
        raise ValueError("aggressive profile requires Advanced Risk consent")

    # Conservative baseline: keep overrides empty (defaults come from env policy or are permissive)
    if p == "conservative":
        POLICY_OVERRIDES = {
            "MAX_TRADE_AMOUNT": float(os.getenv("MAX_TRADE_AMOUNT", "250") or 250),
            "MAX_TRANSFER_NATIVE": float(os.getenv("MAX_TRANSFER_NATIVE", "0.05") or 0.05),
            "MAX_CEX_ORDER_AMOUNT": float(os.getenv("MAX_CEX_ORDER_AMOUNT", "0.01") or 0.01),
        }
    elif p == "balanced":
        POLICY_OVERRIDES = {
            "MAX_TRADE_AMOUNT": float(os.getenv("MAX_TRADE_AMOUNT", "1000") or 1000),
            "MAX_TRANSFER_NATIVE": float(os.getenv("MAX_TRANSFER_NATIVE", "0.1") or 0.1),
            "MAX_CEX_ORDER_AMOUNT": float(os.getenv("MAX_CEX_ORDER_AMOUNT", "0.05") or 0.05),
        }
    else:  # aggressive
        POLICY_OVERRIDES = {
            "MAX_TRADE_AMOUNT": float(os.getenv("MAX_TRADE_AMOUNT", "5000") or 5000),
            "MAX_TRANSFER_NATIVE": float(os.getenv("MAX_TRANSFER_NATIVE", "0.5") or 0.5),
            "MAX_CEX_ORDER_AMOUNT": float(os.getenv("MAX_CEX_ORDER_AMOUNT", "0.25") or 0.25),
        }

    RISK_PROFILE = p

# --- Helper Functions ---

def _get_account():
    """Load account from PRIVATE_KEY env var."""
    # Backwards-compatible helper used by older tests/utilities.
    # Phase 2: prefer get_signer().get_address() and get_signer().sign_transaction(...)
    pk = os.getenv("PRIVATE_KEY")
    if not pk:
        raise ValueError("PRIVATE_KEY environment variable not set")
    w3 = Web3()
    return w3.eth.account.from_key(pk)

def _get_web3(chain: str) -> Web3:
    """Get a Web3 instance for the specified chain."""
    # Phase 0/1: Allow env override; fallback to public RPCs for dev/demo.
    chain_key = chain.lower()
    env_key = f"CHAIN_RPC_{chain_key.upper()}"
    rpc_url = os.getenv(env_key)
    if not rpc_url:
        # Production deployments should set CHAIN_RPC_<CHAIN> to a trusted provider.
        rpcs = {
            "ethereum": "https://eth.llamarpc.com",
            "base": "https://base.llamarpc.com",
            "arbitrum": "https://arb1.arbitrum.io/rpc",
            "optimism": "https://mainnet.optimism.io",
        }
        rpc_url = rpcs.get(chain_key)
    if not rpc_url:
        raise ValueError(
            f"Chain {chain} not supported. Set {env_key} or use one of: ethereum, base, arbitrum, optimism"
        )
    return Web3(Web3.HTTPProvider(rpc_url))

def _fetch_price(symbol: str, exchange: str = "binance") -> str:
    # We ignore the 'exchange' argument now, as the provider handles routing/fallback
    try:
        ticker = exchange_provider.fetch_ticker(symbol)
        last_price = ticker.get('last')
        # We report which exchange worked? 
        return f"The current price of {symbol} is {last_price} (Source: Aggregated)"
    except Exception as e:
        # Keep legacy string output for helper; MCP tool returns structured JSON wrapper
        return f"Error fetching price for {symbol}: {str(e)}"

def _fetch_balance(address: str, chain: str = "ethereum") -> str:
    try:
        w3 = _get_web3(chain)
        if not w3.is_address(address):
            return f"Invalid address format: {address}"
            
        checksum_address = w3.to_checksum_address(address)
        balance_wei = w3.eth.get_balance(checksum_address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        currency = w3.eth.currency if hasattr(w3.eth, "currency") else "ETH"
        return f"Balance for {address} on {chain}: {balance_eth:.6f} {currency}"
    except Exception as e:
        return f"Error fetching balance directly: {str(e)}"

def _transfer_eth(to_address: str, amount: float, chain: str = "ethereum") -> str:
    try:
        w3 = _get_web3(chain)
        signer = get_signer()
        
        if not w3.is_address(to_address):
            return f"Invalid address format: {to_address}"
            
        to_address = w3.to_checksum_address(to_address)
        amount_wei = w3.to_wei(amount, 'ether')
        
        from_address = w3.to_checksum_address(signer.get_address())
        nonce = w3.eth.get_transaction_count(from_address)
        
        # Build transaction
        tx = {
            'nonce': nonce,
            'to': to_address,
            'value': amount_wei,
            'gas': 21000,
            'gasPrice': w3.eth.gas_price,
            'chainId': w3.eth.chain_id
        }
        
        # Sign transaction
        signed_tx = signer.sign_transaction(tx, chain_id=w3.eth.chain_id)
        
        # Send transaction (LIVE)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return f"Transaction sent! Hash: {w3.to_hex(tx_hash)}"
        
    except Exception as e:
        return f"Error executing transfer: {str(e)}"



def _swap_tokens(from_token: str, to_token: str, amount: float, chain: str = "ethereum") -> str:
    """Real DEX Swap using 1inch API."""
    try:
        # 1. Resolve Tokens
        from_address = dex_handler.resolve_token(chain, from_token)
        to_address = dex_handler.resolve_token(chain, to_token)
        
        if not from_address or not to_address:
            return f"Error: Could not resolve token addresses for {from_token} or {to_token} on {chain}."

        w3 = _get_web3(chain)
        signer = get_signer()
        wallet_address = signer.get_address()
        
        # 2. Get Quote (mostly to get decimals/units)
        # We need 'amount' in atomic units.
        # Use 1inch Quote to get decimals first? 
        # Or blindly trust 18? No. 
        # Let's assume standard ERC20 check IF we had web3 contract access.
        # For efficiency, let's call Quote with a tiny amount (1 unit) to get token decimals from response?
        # Better: Quote requires amount. 1inch token API exists but let's try to 'guess' or use standard.
        # Actually 1inch Quote API response includes "fromToken" -> "decimals".
        # But we need to send the Input Amount in atomic units to GET the quote.
        # Catch 22.
        # Solution: Use simple hardcoded decimals for mapped tokens, or fetch from chain for others.
        
        # Simple Logic for known tokens:
        decimals = 18
        if from_token.upper() in ["USDC", "USDT"]:
             decimals = 6
        elif from_token.upper() == "WBTC":
             decimals = 8
             
        amount_wei = int(amount * (10 ** decimals))
        
        # 3. Check Allowance (Skip for ETH)
        if from_address.lower() != "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
            allowance_data = dex_handler.check_allowance(chain, from_address, wallet_address)
            if "allowance" in allowance_data:
                current_allowance = int(allowance_data['allowance'])
                if current_allowance < amount_wei:
                    # Need Approve
                    approve_res = dex_handler.get_approve_tx(chain, from_address, str(amount_wei))
                    if "data" in approve_res:
                         # Phase 1: Router/spender allowlist enforcement (approval spender)
                         try:
                              policy_engine.validate_router_address(
                                   chain=chain,
                                   router_address=str(approve_res.get("to", "")),
                                   context={"stage": "approve", "token": from_token},
                              )
                         except PolicyError as e:
                              return f"PolicyError({e.code}): {e.message}"
                         # Send Approve TX
                         tx = {
                            'to': approve_res['to'],
                            'data': approve_res['data'],
                            'value': int(approve_res.get('value', 0)),
                            'gasPrice': w3.eth.gas_price, # Use simple gas price or 1inch gas price
                            'nonce': w3.eth.get_transaction_count(wallet_address),
                            'chainId': w3.eth.chain_id
                         }
                         # Estimate Gas
                         try:
                            tx["gas"] = w3.eth.estimate_gas({k: v for k, v in tx.items() if k != "chainId"})
                         except Exception:
                            tx["gas"] = 100000  # Fallback
                            
                         signed = signer.sign_transaction(tx, chain_id=w3.eth.chain_id)
                         tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
                         # Wait for it? 
                         # For a synchronized tool, we should wait.
                         w3.eth.wait_for_transaction_receipt(tx_hash)
                    else:
                        return f"Error building Approve TX: {approve_res}"
            else:
                 return f"Error checking allowance: {allowance_data}"

        # 4. Build Swap TX
        slippage = float(os.getenv("DEX_SLIPPAGE_PCT", "1.0"))
        if slippage <= 0:
            slippage = 1.0
        swap_res = dex_handler.build_swap_tx(
            chain,
            from_address,
            to_address,
            str(amount_wei),
            wallet_address,
            slippage=slippage,
        )
        if "tx" not in swap_res:
            return f"Error querying Swap API: {swap_res}"
            
        tx_data = swap_res['tx']
        # Phase 1: Router allowlist enforcement (swap router)
        try:
            policy_engine.validate_router_address(
                chain=chain,
                router_address=str(tx_data.get("to", "")),
                context={"stage": "swap", "from_token": from_token, "to_token": to_token},
            )
        except PolicyError as e:
            return f"PolicyError({e.code}): {e.message}"
        
        # Construct Web3 TX
        tx = {
            'to': tx_data['to'],
            'data': tx_data['data'],
            'value': int(tx_data['value']),
            'gasPrice': int(tx_data['gasPrice']),
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'chainId': w3.eth.chain_id
        }
        # Gas might be in tx_data or need estimate
        if 'gas' in tx_data:
             tx['gas'] = int(tx_data['gas'])
        else:
             tx['gas'] = w3.eth.estimate_gas({k:v for k,v in tx.items() if k != 'chainId'})

        # 5. Sign & Send
        signed_tx = signer.sign_transaction(tx, chain_id=w3.eth.chain_id)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        return f"Swap Sent! {amount} {from_token} -> {to_token}. Hash: {w3.to_hex(tx_hash)}"

    except Exception as e:
        return f"Error executing swap: {str(e)}"

# --- MCP Tools ---

# --- Intelligence Tools ---

@mcp.tool()
def get_sentiment() -> str:
    """Get the current Crypto Fear & Greed Index."""
    rl = _rate_limit("get_sentiment")
    if rl:
        return rl
    return _json_ok({"sentiment": get_fear_greed_index()})

@mcp.tool()
def get_news() -> str:
    """Get aggregated crypto market news."""
    return _tool_get_news()

def _tool_get_news() -> str:
    rl = _rate_limit("get_news")
    if rl:
        return rl
    return _json_ok({"news": get_market_news()})

@mcp.tool()
def get_social_sentiment(symbol: str) -> str:
    """
    Get simulated social media sentiment (X/Reddit).
    Returns a sentiment score and trending topics.
    """
    rl = _rate_limit("get_social_sentiment")
    if rl:
        return rl
    return _json_ok({"symbol": symbol, "social_sentiment": analyze_social_sentiment(symbol)})

@mcp.tool()
def get_financial_news(symbol: str) -> str:
    """
    Get simulated high-tier financial news (Bloomberg/Reuters).
    """
    rl = _rate_limit("get_financial_news")
    if rl:
        return rl
    return _json_ok({"symbol": symbol, "financial_news": fetch_financial_news(symbol)})

# --- Paper Trading Tools ---

@mcp.tool()
def deposit_paper_funds(asset: str, amount: float) -> str:
    """
    [PAPER MODE] Deposit fake funds into the paper trading wallet.
    """
    rl = _rate_limit("deposit_paper_funds")
    if rl:
        return rl
    if not PAPER_MODE:
        return _json_err("paper_mode_required", "Paper mode is NOT enabled.")
    # Use default user 'agent_zero'
    return _json_ok({"result": paper_engine.deposit("agent_zero", asset, amount)})

# --- Research & Backtest Tools ---

@mcp.tool()
def fetch_ohlcv(symbol: str, timeframe: str = '1h', limit: int = 24) -> str:
    """
    Fetch historical OHLCV data. 
    Use this to analyze markets before Backtesting.
    Returns a summarized string of the dataframe.
    """
    rl = _rate_limit("fetch_ohlcv")
    if rl:
        return rl
    try:
        df = backtest_engine.fetch_ohlcv(symbol, timeframe, limit)
        return _json_ok(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "limit": limit,
                "data": df.to_dict(orient="records"),
            }
        )
    except Exception as e:
        code = getattr(e, "code", "fetch_ohlcv_error")
        msg = getattr(e, "message", str(e))
        data = getattr(e, "data", {"symbol": symbol, "timeframe": timeframe, "limit": limit})
        return _json_err(code, msg, data)

@mcp.tool()
def run_backtest_simulation(strategy_code: str, symbol: str, timeframe: str = '1h') -> str:
    """
    Run a strategy simulation against historical data.
    
    Args:
        strategy_code: Python code defining 'def on_candle(close, rsi, state): -> str'.
                       Must return 'buy', 'sell', or 'hold'.
        symbol: Trading pair (e.g. BTC/USDT).
        timeframe: Candle size (e.g. 1h, 4h, 1d).
        
    Returns:
        JSON string containing PnL, Win Rate, and trade log.
    """
    rl = _rate_limit("run_backtest_simulation")
    if rl:
        return rl
    result = backtest_engine.run(strategy_code, symbol, timeframe)
    return _json_ok({"result": result})

# --- Phase 6: Regime & Risk Tools ---

@mcp.tool()
def get_market_regime(symbol: str, timeframe: str = '1d') -> str:
    """
    Detect the current market regime (TRENDING, RANGING, VOLATILE).
    Uses ADX and ATR indicators on historical data.
    """
    rl = _rate_limit("get_market_regime")
    if rl:
        return rl
    try:
        # Fetch data first
        df = backtest_engine.fetch_ohlcv(symbol, timeframe, limit=100)
        result = regime_detector.detect(df)
        return _json_ok({"symbol": symbol, "timeframe": timeframe, "result": result})
    except Exception as e:
        return _json_err("market_regime_error", str(e), {"symbol": symbol, "timeframe": timeframe})

@mcp.tool()
def validate_trade_risk(side: str, symbol: str, amount_usd: float, portfolio_value: float) -> str:
    """
    [GUARDIAN] Validate if a trade is safe to execute.
    Checks position sizing and sentiment alignment.
    """
    rl = _rate_limit("validate_trade_risk")
    if rl:
        return rl
    try:
        # We need sentiment for the check
        # We fetch cached sentiment (updated via get_social_sentiment tool)
        sentiment_score = get_cached_sentiment_score(symbol)
        
        # Get Portfolio/Risk Metrics
        daily_loss = 0.0
        drawdown = 0.0
        
        if PAPER_MODE and paper_engine:
             metrics = paper_engine.get_risk_metrics("agent_zero")
             daily_loss = metrics.get('daily_pnl_pct', 0.0)
             drawdown = metrics.get('drawdown_pct', 0.0)
        
        result = risk_guardian.validate_trade(
            side, symbol, amount_usd, portfolio_value, sentiment_score, daily_loss, drawdown
        )
        return _json_ok(
            {
                "side": side,
                "symbol": symbol,
                "amount_usd": amount_usd,
                "portfolio_value": portfolio_value,
                "sentiment_score": sentiment_score,
                "result": result,
            }
        )
    except Exception as e:
        return _json_err("risk_validation_error", str(e))

@mcp.tool()
def get_crypto_price(symbol: str, exchange: str = "binance") -> str:
    """
    Get the current price of a cryptocurrency.
    
    Args:
        symbol: The trading pair symbol (e.g., 'BTC/USDT', 'ETH/USDT').
        exchange: The exchange to check (default: 'binance').
        
    Returns:
        A string message with the price or an error.
    """
    rl = _rate_limit("get_crypto_price")
    if rl:
        return rl
    msg = _fetch_price(symbol, exchange)
    return _json_ok({"symbol": symbol, "exchange": exchange, "result": msg})

@mcp.tool()
def get_marketdata_capabilities(exchange_id: str = "") -> str:
    """
    Return CCXT market data capabilities for a configured exchange (or primary).
    """
    rl = _rate_limit("get_marketdata_capabilities")
    if rl:
        return rl
    try:
        cap = exchange_provider.get_marketdata_capabilities(exchange_id or None)
        return _json_ok({"capabilities": cap})
    except Exception as e:
        code = getattr(e, "code", "capabilities_error")
        msg = getattr(e, "message", str(e))
        data = getattr(e, "data", {})
        return _json_err(code, msg, data)

@mcp.tool()
def get_address_balance(address: str, chain: str = "ethereum") -> str:
    """
    Get the native coin balance of an address on a specific EVM chain.
    
    Args:
        address: The hex address to check (e.g., '0x123...').
        chain: The chain name ('ethereum', 'base', 'arbitrum', 'optimism').
        
    Returns:
        A string message with the balance in ETH (or native token).
    """
    rl = _rate_limit("get_address_balance")
    if rl:
        return rl
    msg = _fetch_balance(address, chain)
    return _json_ok({"address": address, "chain": chain, "result": msg})

@mcp.tool()
def transfer_eth(to_address: str, amount: float, chain: str = "ethereum") -> str:
    """
    Send ETH (or native token) to an address.
    REQUIRES 'PRIVATE_KEY' env var to be set.
    
    Args:
        to_address: Recipient hex address.
        amount: Amount to send in ETH.
        chain: The chain name ('ethereum', 'base', 'arbitrum', 'optimism').
        
    Returns:
        Transaction hash or simulation result.
    """
    rl = _rate_limit("transfer_eth")
    if rl:
        return rl
    if PAPER_MODE:
        return _json_ok({"mode": "paper", "result": f"Simulated transfer of {amount} ETH to {to_address} on {chain}."})

    gate = _require_live_execution_allowed("transfer_eth")
    if gate:
        return gate

    exec_mode = _get_execution_mode()
    if not venue_allowed(exec_mode, "dex"):
        return _json_err(
            "execution_mode_blocked",
            f"transfer_eth not allowed when EXECUTION_MODE={exec_mode}.",
            {"execution_mode": exec_mode},
        )

    try:
        # Phase 1 policy check
        overrides = _effective_overrides()
        policy_engine.validate_transfer_native(chain=chain, to_address=to_address, amount=amount, overrides=overrides)

        if _human_confirmation_enabled():
            # Build unsigned tx proposal (sign/send on confirm)
            w3 = _get_web3(chain)
            signer = get_signer()
            from_address = w3.to_checksum_address(signer.get_address())
            nonce = w3.eth.get_transaction_count(from_address)
            to_checksum = w3.to_checksum_address(to_address)
            tx = {
                "nonce": nonce,
                "to": to_checksum,
                "value": int(w3.to_wei(amount, "ether")),
                "gas": 21000,
                "gasPrice": int(w3.eth.gas_price),
                "chainId": int(w3.eth.chain_id),
            }
            prop = execution_store.create(
                kind="transfer_eth",
                payload={"chain": chain, "tx": tx, "to_address": to_checksum, "amount": float(amount)},
                ttl_seconds=120,
            )
            return _json_ok(
                {
                    "mode": "live",
                    "needs_confirmation": True,
                    "request_id": prop.request_id,
                    "confirm_token": prop.confirm_token,
                    "proposal": {"chain": chain, "tx": tx},
                }
            )

        return _json_ok({"mode": "live", "chain": chain, "result": _transfer_eth(to_address, amount, chain)})
    except PolicyError as e:
        return _json_err(e.code, e.message, e.data)
    except Exception as e:
        return _json_err("transfer_error", str(e))



 

def _tool_analyze_performance(symbol: str = None) -> str:
    """
    Review past trade performance and generated lessons.
    Args:
        symbol: Optional symbol to filter by.
    """
    return _json_ok({"symbol": symbol, "result": learner.analyze_performance(symbol)})

@mcp.tool()
def analyze_performance(symbol: str = None) -> str:
    rl = _rate_limit("analyze_performance")
    if rl:
        return rl
    return _tool_analyze_performance(symbol)

def _tool_swap_tokens(
    from_token: str,
    to_token: str,
    amount: float,
    chain: str = "ethereum",
    rationale: str = "",
) -> str:
    rl = _rate_limit("swap_tokens")
    if rl:
        return rl
    """
    Swap tokens on a Decentralized Exchange (DEX).
    REQUIRES 'PRIVATE_KEY' env var to be set.
    
    Args:
        from_token: Symbol or address of token to sell (e.g., 'USDC').
        to_token: Symbol or address of token to buy (e.g., 'WETH').
        amount: Amount of 'from_token' to swap.
        chain: The chain name.
        rationale: Reason for the trade (used for learning logic).
        
    Returns:
        Swap simulation result.
    """
    if PAPER_MODE:
        user_id = "agent_zero"
        # Phase 4: enforce risk checks in paper mode using paper metrics
        try:
            metrics = paper_engine.get_risk_metrics(user_id)
            portfolio_value = paper_engine.get_portfolio_value_usd(user_id)
            # Approximate notional: if from_token is stable, treat as USD. Otherwise use cached price if available.
            from_px = paper_engine._get_asset_price_usd(from_token)  # internal helper; safe for paper mode
            amount_usd = float(amount) * float(from_px or 0.0)
            risk = risk_guardian.validate_trade(
                "sell",
                f"{from_token}/{to_token}",
                amount_usd,
                portfolio_value,
                get_cached_sentiment_score(f"{from_token}/{to_token}"),
                metrics.get("daily_pnl_pct", 0.0),
                metrics.get("drawdown_pct", 0.0),
            )
            if not risk.get("allowed", False):
                return _json_err("risk_blocked", risk.get("reason", "Risk blocked trade."), {"risk": risk})
        except Exception:
            # If risk calc fails, fail closed in paper mode (safer)
            return _json_err("risk_calc_error", "Risk calculation failed; paper trade blocked.")

        # Execute as a 1:1 price placeholder if no price cache exists (paper engine caches from executed trades)
        price = paper_engine._get_asset_price_usd(to_token) or 1.0
        return _json_ok(
            {
                "mode": "paper",
                "venue": "dex",
                "chain": chain,
                "result": paper_engine.execute_trade(
                    user_id,
                    "sell",
                    f"{from_token}/{to_token}",
                    amount,
                    float(price),
                    rationale,
                ),
            }
        )

    gate = _require_live_execution_allowed("swap_tokens")
    if gate:
        return gate

    exec_mode = _get_execution_mode()
    if not venue_allowed(exec_mode, "dex"):
        return _json_err(
            "execution_mode_blocked",
            f"swap_tokens not allowed when EXECUTION_MODE={exec_mode}.",
            {"execution_mode": exec_mode},
        )

    try:
        # Phase 1 policy check (allowlists, bounds)
        overrides = _effective_overrides()
        policy_engine.validate_swap(
            chain=chain,
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            overrides=overrides,
        )

        if _human_confirmation_enabled():
            # Build swap tx proposal (sign/send on confirm)
            from_address = dex_handler.resolve_token(chain, from_token)
            to_address = dex_handler.resolve_token(chain, to_token)
            if not from_address or not to_address:
                return _json_err(
                    "token_resolution_failed",
                    "Could not resolve token addresses.",
                    {"from_token": from_token, "to_token": to_token, "chain": chain},
                )

            w3 = _get_web3(chain)
            signer = get_signer()
            wallet_address = signer.get_address()

            decimals = 18
            if from_token.upper() in ["USDC", "USDT"]:
                decimals = 6
            elif from_token.upper() == "WBTC":
                decimals = 8
            amount_wei = int(amount * (10**decimals))

            slippage = float(os.getenv("DEX_SLIPPAGE_PCT", "1.0"))
            if slippage <= 0:
                slippage = 1.0
            swap_res = dex_handler.build_swap_tx(
                chain,
                from_address,
                to_address,
                str(amount_wei),
                wallet_address,
                slippage=slippage,
            )
            if "tx" not in swap_res:
                return _json_err("swap_quote_error", "Error building swap tx.", {"swap_res": swap_res})
            tx_data = swap_res["tx"]

            # Router allowlist enforcement
            try:
                policy_engine.validate_router_address(
                    chain=chain,
                    router_address=str(tx_data.get("to", "")),
                    context={"stage": "swap", "from_token": from_token, "to_token": to_token},
                )
            except PolicyError as e:
                return _json_err(e.code, e.message, e.data)

            tx = {
                "to": tx_data["to"],
                "data": tx_data["data"],
                "value": int(tx_data["value"]),
                "gasPrice": int(tx_data["gasPrice"]),
                "nonce": w3.eth.get_transaction_count(w3.to_checksum_address(wallet_address)),
                "chainId": int(w3.eth.chain_id),
            }
            if "gas" in tx_data:
                tx["gas"] = int(tx_data["gas"])
            else:
                tx["gas"] = int(w3.eth.estimate_gas({k: v for k, v in tx.items() if k != "chainId"}))

            prop = execution_store.create(
                kind="swap_tokens",
                payload={"chain": chain, "tx": tx, "from_token": from_token, "to_token": to_token, "amount": amount},
                ttl_seconds=120,
            )
            return _json_ok(
                {
                    "mode": "live",
                    "venue": "dex",
                    "chain": chain,
                    "needs_confirmation": True,
                    "request_id": prop.request_id,
                    "confirm_token": prop.confirm_token,
                    "proposal": {"tx": tx, "from_token": from_token, "to_token": to_token, "amount": amount},
                }
            )

        res = _swap_tokens(from_token, to_token, amount, chain)
        return _json_ok({"mode": "live", "venue": "dex", "chain": chain, "result": res})
    except PolicyError as e:
        return _json_err(e.code, e.message, e.data)
    except Exception as e:
        return _json_err("swap_error", str(e))

@mcp.tool()
def swap_tokens(from_token: str, to_token: str, amount: float, chain: str = "ethereum", rationale: str = "") -> str:
    return _tool_swap_tokens(from_token=from_token, to_token=to_token, amount=amount, chain=chain, rationale=rationale)


def _tool_place_cex_order(
    symbol: str,
    side: str,
    amount: float,
    order_type: str = "market",
    price: float | None = None,
    exchange: str = "binance",
    market_type: str = "spot",
    idempotency_key: str = "",
) -> str:
    rl = _rate_limit("place_cex_order")
    if rl:
        return rl
    """
    Place an order on a centralized exchange via ccxt.
    """
    exec_mode = _get_execution_mode()
    if not venue_allowed(exec_mode, "cex"):
        return _json_err(
            "execution_mode_blocked",
            f"place_cex_order not allowed when EXECUTION_MODE={exec_mode}.",
            {"execution_mode": exec_mode},
        )

    if PAPER_MODE:
        # Paper simulate using our paper engine at last price
        if not paper_engine:
            return _json_err("paper_engine_unavailable", "paper_engine is not initialized.")
        try:
            ticker = exchange_provider.fetch_ticker(symbol)
            last = float(ticker.get("last") or 0.0)
            if last <= 0:
                return _json_err(
                    "price_unavailable",
                    "Could not fetch a valid last price for paper simulation.",
                    {"symbol": symbol},
                )
            # Phase 4: enforce RiskGuardian in paper mode for CEX simulation
            metrics = paper_engine.get_risk_metrics("agent_zero")
            portfolio_value = paper_engine.get_portfolio_value_usd("agent_zero")
            # Notional in USD: base amount * last (assume quote is USD stable)
            amount_usd = float(amount) * float(last)
            risk = risk_guardian.validate_trade(
                side.lower(),
                symbol,
                amount_usd,
                portfolio_value,
                get_cached_sentiment_score(symbol),
                metrics.get("daily_pnl_pct", 0.0),
                metrics.get("drawdown_pct", 0.0),
            )
            if not risk.get("allowed", False):
                return _json_err("risk_blocked", risk.get("reason", "Risk blocked trade."), {"risk": risk})
            res = paper_engine.execute_trade(
                "agent_zero",
                side.lower(),
                symbol,
                amount,
                last,
                rationale=f"CEX_SIM:{exchange}:{order_type}",
            )
            return _json_ok(
                {
                    "mode": "paper",
                    "venue": "cex",
                    "exchange": exchange,
                    "symbol": symbol,
                    "result": res,
                    "price": last,
                }
            )
        except Exception as e:
            return _json_err("paper_cex_sim_error", str(e))

    gate = _require_live_execution_allowed("place_cex_order")
    if gate:
        return gate

    try:
        if idempotency_key:
            cached = IDEMPOTENCY_STORE.get(idempotency_key)
            if cached is not None:
                return _json_ok({"idempotency_key": idempotency_key, "reused": True, **cached})

        policy_engine.validate_cex_order(
            exchange_id=exchange,
            symbol=symbol,
            market_type=market_type,
            side=side,
            amount=amount,
            order_type=order_type,
            price=price,
            overrides=_effective_overrides(),
        )

        # Optional idempotency: if provided, reuse result/proposal for duplicate requests.
        # (In MCP, this is useful for agent retries.)

        if _human_confirmation_enabled():
            prop = execution_store.create(
                kind="place_cex_order",
                payload={
                    "exchange": exchange,
                    "symbol": symbol,
                    "market_type": market_type,
                    "side": side,
                    "amount": amount,
                    "order_type": order_type,
                    "price": price,
                },
                ttl_seconds=120,
            )
            out = {
                "mode": "live",
                "venue": "cex",
                "exchange": exchange,
                "needs_confirmation": True,
                "request_id": prop.request_id,
                "confirm_token": prop.confirm_token,
                "proposal": prop.payload,
            }
            if idempotency_key:
                IDEMPOTENCY_STORE[idempotency_key] = out
            return _json_ok(
                {
                    **out,
                    "idempotency_key": idempotency_key or None,
                }
            )

        ex = CexExecutor(exchange_id=exchange, market_type=market_type)
        order = ex.place_order(symbol=symbol, side=side, amount=amount, order_type=order_type, price=price)
        out = {
            "mode": "live",
            "venue": "cex",
            "exchange": exchange,
            "market_type": market_type,
            "order": ex.normalize_order(order),
        }
        if idempotency_key:
            IDEMPOTENCY_STORE[idempotency_key] = out
        return _json_ok({"idempotency_key": idempotency_key or None, **out})
    except PolicyError as e:
        return _json_err(e.code, e.message, e.data)
    except Exception as e:
        return _json_err("cex_order_error", str(e), {"exchange": exchange, "symbol": symbol})


@mcp.tool()
def cancel_cex_order(order_id: str, symbol: str = "", exchange: str = "binance", market_type: str = "spot") -> str:
    rl = _rate_limit("cancel_cex_order")
    if rl:
        return rl
    exec_mode = _get_execution_mode()
    if not venue_allowed(exec_mode, "cex"):
        return _json_err(
            "execution_mode_blocked",
            f"cancel_cex_order not allowed when EXECUTION_MODE={exec_mode}.",
            {"execution_mode": exec_mode},
        )
    if PAPER_MODE:
        return _json_err("paper_mode_not_supported", "CEX cancel is not supported in paper mode.")

    # cancellation is also a live action, require consent gates
    gate = _require_live_execution_allowed("cancel_cex_order")
    if gate:
        return gate
    try:
        policy_engine.validate_cex_access(exchange_id=exchange)
        ex = CexExecutor(exchange_id=exchange, market_type=market_type)
        res = ex.cancel_order(order_id=order_id, symbol=(symbol or None))
        return _json_ok({"exchange": exchange, "market_type": market_type, "order": ex.normalize_order(res)})
    except PolicyError as e:
        return _json_err(e.code, e.message, e.data)
    except Exception as e:
        return _json_err("cex_cancel_error", str(e), {"exchange": exchange, "order_id": order_id})


@mcp.tool()
def get_cex_order(order_id: str, symbol: str = "", exchange: str = "binance", market_type: str = "spot") -> str:
    rl = _rate_limit("get_cex_order")
    if rl:
        return rl
    exec_mode = _get_execution_mode()
    if not venue_allowed(exec_mode, "cex"):
        return _json_err(
            "execution_mode_blocked",
            f"get_cex_order not allowed when EXECUTION_MODE={exec_mode}.",
            {"execution_mode": exec_mode},
        )
    if PAPER_MODE:
        return _json_err("paper_mode_not_supported", "CEX order fetch is not supported in paper mode.")
    try:
        policy_engine.validate_cex_access(exchange_id=exchange)
        ex = CexExecutor(exchange_id=exchange, market_type=market_type)
        res = ex.fetch_order(order_id=order_id, symbol=(symbol or None))
        return _json_ok({"exchange": exchange, "market_type": market_type, "order": ex.normalize_order(res)})
    except PolicyError as e:
        return _json_err(e.code, e.message, e.data)
    except Exception as e:
        return _json_err("cex_fetch_order_error", str(e), {"exchange": exchange, "order_id": order_id})


@mcp.tool()
def place_cex_order(
    symbol: str,
    side: str,
    amount: float,
    order_type: str = "market",
    price: float | None = None,
    exchange: str = "binance",
    market_type: str = "spot",
    idempotency_key: str = "",
) -> str:
    return _tool_place_cex_order(
        symbol=symbol,
        side=side,
        amount=amount,
        order_type=order_type,
        price=price,
        exchange=exchange,
        market_type=market_type,
        idempotency_key=idempotency_key,
    )


def _tool_get_cex_balance(exchange: str = "binance", market_type: str = "spot") -> str:
    rl = _rate_limit("get_cex_balance")
    if rl:
        return rl
    exec_mode = _get_execution_mode()
    if not venue_allowed(exec_mode, "cex"):
        return _json_err(
            "execution_mode_blocked",
            f"get_cex_balance not allowed when EXECUTION_MODE={exec_mode}.",
            {"execution_mode": exec_mode},
        )

    if PAPER_MODE:
        return _json_err(
            "paper_mode_not_supported",
            "CEX balances are not supported in paper mode. Use get_address_balance or paper db balances.",
        )

    try:
        # Read-only access: do not require consent, but still respect exchange allowlists if configured.
        policy_engine.validate_cex_access(exchange_id=exchange)
        ex = CexExecutor(exchange_id=exchange, market_type=market_type)
        bal = ex.fetch_balance()
        # Keep response smaller: return just 'total' if present
        return _json_ok(
            {
                "mode": "live",
                "venue": "cex",
                "exchange": exchange,
                "market_type": market_type,
                "balance": bal.get("total", bal),
            }
        )
    except PolicyError as e:
        return _json_err(e.code, e.message, e.data)
    except Exception as e:
        return _json_err("cex_balance_error", str(e), {"exchange": exchange})


@mcp.tool()
def get_cex_balance(exchange: str = "binance", market_type: str = "spot") -> str:
    return _tool_get_cex_balance(exchange=exchange, market_type=market_type)


def _tool_get_cex_capabilities(exchange: str = "binance", symbol: str = "", market_type: str = "spot") -> str:
    rl = _rate_limit("get_cex_capabilities")
    if rl:
        return rl
    try:
        policy_engine.validate_cex_access(exchange_id=exchange)
        # Capabilities and market metadata are public data; do not require auth.
        ex = CexExecutor(exchange_id=exchange, market_type=market_type, auth=False)
        cap = ex.get_capabilities(symbol=symbol)
        return _json_ok({"exchange": exchange, "market_type": market_type, "capabilities": cap})
    except PolicyError as e:
        return _json_err(e.code, e.message, e.data)
    except Exception as e:
        return _json_err("cex_capabilities_error", str(e), {"exchange": exchange, "symbol": symbol})


@mcp.tool()
def get_cex_capabilities(exchange: str = "binance", symbol: str = "", market_type: str = "spot") -> str:
    """
    Return CCXT capability metadata for a given exchange and optional symbol.
    """
    return _tool_get_cex_capabilities(exchange=exchange, symbol=symbol, market_type=market_type)

@mcp.tool()
def get_advanced_risk_disclosure() -> str:
    """
    Returns the advanced risk disclosure for enabling elevated risk limits.
    """
    rl = _rate_limit("get_advanced_risk_disclosure")
    if rl:
        return rl
    return _json_ok(
        {
            "version": ADV_DISCLOSURE_VERSION,
            "text": ADV_DISCLOSURE_TEXT,
            "accepted": ADV_DISCLOSURE_ACCEPTED,
            "accepted_at": ADV_DISCLOSURE_ACCEPTED_AT,
        }
    )

@mcp.tool()
def accept_advanced_risk_disclosure(accepted: bool) -> str:
    """
    One-time per-process consent gate for Advanced Risk Mode.
    Resets on restart (non-persistent).
    """
    rl = _rate_limit("accept_advanced_risk_disclosure")
    if rl:
        return rl
    global ADV_DISCLOSURE_ACCEPTED, ADV_DISCLOSURE_ACCEPTED_AT, POLICY_OVERRIDES
    if not accepted:
        ADV_DISCLOSURE_ACCEPTED = False
        ADV_DISCLOSURE_ACCEPTED_AT = None
        POLICY_OVERRIDES = {}
        return _json_ok({"accepted": False, "accepted_at": None, "version": ADV_DISCLOSURE_VERSION})
    ADV_DISCLOSURE_ACCEPTED = True
    ADV_DISCLOSURE_ACCEPTED_AT = _now_iso()
    return _json_ok({"accepted": True, "accepted_at": ADV_DISCLOSURE_ACCEPTED_AT, "version": ADV_DISCLOSURE_VERSION})

@mcp.tool()
def get_policy_overrides() -> str:
    """
    Return current in-memory policy overrides (advanced mode only).
    """
    rl = _rate_limit("get_policy_overrides")
    if rl:
        return rl
    return _json_ok({"advanced_mode": _advanced_mode_allowed(), "overrides": POLICY_OVERRIDES})

@mcp.tool()
def set_policy_overrides(config_json: str) -> str:
    """
    Set in-memory policy overrides. Only allowed after Advanced Risk consent.
    Resets on restart.
    """
    return _tool_set_policy_overrides(config_json)

def _tool_set_policy_overrides(config_json: str) -> str:
    rl = _rate_limit("set_policy_overrides")
    if rl:
        return rl
    if not _advanced_mode_allowed():
        return _json_err(
            "advanced_consent_required",
            (
                "Advanced Risk consent required. Call get_advanced_risk_disclosure(), then "
                "accept_advanced_risk_disclosure(true)."
            ),
            {"version": ADV_DISCLOSURE_VERSION},
        )
    try:
        cfg = json.loads(config_json or "{}")
        if not isinstance(cfg, dict):
            return _json_err("invalid_config", "config_json must decode to a JSON object.")
        # Allow only known keys in Phase 6
        allowed = {
            "MAX_TRADE_AMOUNT",
            "MAX_TRANSFER_NATIVE",
            "MAX_CEX_ORDER_AMOUNT",
        }
        bad = [k for k in cfg.keys() if k not in allowed]
        if bad:
            return _json_err(
                "invalid_override_keys",
                "Unsupported override keys.",
                {"unsupported": bad, "allowed": sorted(allowed)},
            )
        # Normalize numeric
        for k, v in cfg.items():
            POLICY_OVERRIDES[k] = float(v)
        return _json_ok({"advanced_mode": True, "overrides": POLICY_OVERRIDES})
    except Exception as e:
        return _json_err("override_error", str(e))

@mcp.tool()
def place_limit_order(side: str, symbol: str, amount: float, price: float) -> str:
    """
    Place a Limit Order to buy/sell at a specific price.
    Currently supported in PAPER MODE only.
    """
    if PAPER_MODE:
        return _json_ok(
            {"mode": "paper", "result": paper_engine.place_limit_order("agent_zero", side, symbol, amount, price)}
        )
    return _json_err(
        "paper_mode_required",
        "Limit orders currently only supported in PAPER_MODE for this version.",
    )

@mcp.tool()
def check_orders(symbol: str) -> str:
    """
    [PAPER MODE] Check if any open limit orders should be filled based on current market price.
    Triggers a fill if conditions are met.
    """
    if not PAPER_MODE:
        return _json_err("paper_mode_required", "Paper mode only.")
        
    # Get current price to check against
    # We use our internal _fetch_price logic
    try:
        price_str = _fetch_price(symbol)
        # Parse price manually from string "The current price of ... is X"
        import re
        match = re.search(r"is ([0-9.]+)", price_str)
        if match:
            current_price = float(match.group(1))
            filled = paper_engine.check_open_orders(symbol, current_price)
            if filled:
                return _json_ok({"symbol": symbol, "filled": filled, "current_price": current_price})
            return _json_ok({"symbol": symbol, "filled": [], "current_price": current_price})
        return _json_err(
            "price_parse_error",
            "Could not determine price to check orders.",
            {"symbol": symbol, "price_msg": price_str},
        )
    except Exception as e:
        return _json_err("check_orders_error", str(e), {"symbol": symbol})

@mcp.tool()
def get_capabilities() -> str:
    """
    Describe supported venues, chains, and safety flags for MCP clients.
    """
    supported_chains = ["ethereum", "base", "arbitrum", "optimism"]
    venues = ["dex", "cex", "hybrid"]
    exec_mode = _get_execution_mode()
    return _json_ok(
        {
            "paper_mode": PAPER_MODE,
            "execution_mode": exec_mode,
            "execution_approval_mode": _get_execution_approval_mode(),
            "risk_profile": RISK_PROFILE,
            "supported_execution_modes": venues,
            "supported_chains": supported_chains,
            "live_trading_enabled": _is_live_trading_enabled(),
            "trading_halted": _is_trading_halted(),
            "risk_disclosure": {
                "version": DISCLOSURE_VERSION,
                "accepted": DISCLOSURE_ACCEPTED,
                "accepted_at": DISCLOSURE_ACCEPTED_AT,
            },
            "advanced_risk_disclosure": {
                "version": ADV_DISCLOSURE_VERSION,
                "accepted": ADV_DISCLOSURE_ACCEPTED,
                "accepted_at": ADV_DISCLOSURE_ACCEPTED_AT,
            },
        }
    )

@mcp.tool()
def get_execution_preferences() -> str:
    """
    Return execution preferences for the current process (non-persistent).
    """
    rl = _rate_limit("get_execution_preferences")
    if rl:
        return rl
    return _json_ok(
        {
            "execution_mode": _get_execution_mode(),
            "execution_approval_mode": _get_execution_approval_mode(),
            "risk_profile": RISK_PROFILE,
            "supported_execution_approval_modes": ["auto", "approve_each"],
            "supported_risk_profiles": ["conservative", "balanced", "aggressive"],
        }
    )

def _impl_set_execution_preferences(execution_approval_mode: str, risk_profile: str = "") -> str:
    """
    Set execution approval mode for the current process (non-persistent).
    Values: 'auto' or 'approve_each'.
    """
    rl = _rate_limit("set_execution_preferences")
    if rl:
        return rl
    try:
        _set_execution_approval_mode(execution_approval_mode)
        if risk_profile:
            _set_risk_profile(risk_profile)
        return _json_ok({"execution_approval_mode": _get_execution_approval_mode(), "risk_profile": RISK_PROFILE})
    except Exception as e:
        return _json_err(
            "invalid_execution_preference",
            str(e),
            {"execution_approval_mode": execution_approval_mode, "risk_profile": risk_profile},
        )

def _tool_set_execution_preferences(execution_approval_mode: str, risk_profile: str = "") -> str:
    # Helper for unit tests (fastmcp FunctionTool is not directly callable)
    return _impl_set_execution_preferences(execution_approval_mode=execution_approval_mode, risk_profile=risk_profile)

@mcp.tool()
def set_execution_preferences(execution_approval_mode: str, risk_profile: str = "") -> str:
    return _impl_set_execution_preferences(execution_approval_mode=execution_approval_mode, risk_profile=risk_profile)

@mcp.tool()
def get_risk_disclosure() -> str:
    """
    Returns the live trading risk disclosure and whether it has been accepted for this process.
    """
    return _json_ok(
        {
            "version": DISCLOSURE_VERSION,
            "text": DISCLOSURE_TEXT,
            "accepted": DISCLOSURE_ACCEPTED,
            "accepted_at": DISCLOSURE_ACCEPTED_AT,
        }
    )

@mcp.tool()
def accept_risk_disclosure(accepted: bool) -> str:
    """
    One-time per-process consent gate for live trading. Resets on restart (non-persistent).
    """
    global DISCLOSURE_ACCEPTED, DISCLOSURE_ACCEPTED_AT
    if not accepted:
        DISCLOSURE_ACCEPTED = False
        DISCLOSURE_ACCEPTED_AT = None
        return _json_ok({"accepted": False, "accepted_at": None, "version": DISCLOSURE_VERSION})

    DISCLOSURE_ACCEPTED = True
    DISCLOSURE_ACCEPTED_AT = _now_iso()
    return _json_ok({"accepted": True, "accepted_at": DISCLOSURE_ACCEPTED_AT, "version": DISCLOSURE_VERSION})

@mcp.tool()
def run_synthetic_stress_test(strategy_code: str, config_json: str = "{}") -> str:
    rl = _rate_limit("run_synthetic_stress_test")
    if rl:
        return rl
    """
    Run a deterministic synthetic market stress test against strategy_code.

    config_json supports:
      - master_seed (int)
      - scenarios (int)
      - length (int)
      - timeframe (str)
      - initial_capital (float)
      - start_price (float)
      - base_vol (float)
      - black_swan_prob (float)
      - parabolic_prob (float)
    """
    try:
        cfg = json.loads(config_json or "{}")
        if not isinstance(cfg, dict):
            return _json_err("invalid_config", "config_json must decode to a JSON object.")

        res = _run_synth_stress(strategy_code=strategy_code, config=cfg)
        recs = _recommend_settings(res.get("summary", {}))
        return _json_ok(
            {
                "summary": res.get("summary", {}),
                "recommendations": recs,
                "artifacts": res.get("artifacts", {}),
            }
        )
    except Exception as e:
        return _json_err("synthetic_stress_error", str(e))

@mcp.tool()
def list_pending_executions() -> str:
    rl = _rate_limit("list_pending_executions")
    if rl:
        return rl
    return _json_ok(execution_store.list_pending())

@mcp.tool()
def cancel_execution(request_id: str) -> str:
    rl = _rate_limit("cancel_execution")
    if rl:
        return rl
    ok = execution_store.cancel(request_id)
    if not ok:
        return _json_err(
            "cancel_failed",
            "Unable to cancel (not found, expired, already confirmed, or already cancelled).",
            {"request_id": request_id},
        )
    return _json_ok({"request_id": request_id, "cancelled": True})

@mcp.tool()
def confirm_execution(request_id: str, confirm_token: str) -> str:
    """
    Confirm a previously proposed execution. Replay protected (single-use, TTL).
    """
    return _tool_confirm_execution(request_id, confirm_token)

def _tool_confirm_execution(request_id: str, confirm_token: str) -> str:
    rl = _rate_limit("confirm_execution")
    if rl:
        return rl

    # Live execution still requires baseline consent gates
    gate = _require_live_execution_allowed("confirm_execution")
    if gate:
        return gate

    try:
        prop = execution_store.confirm(request_id, confirm_token)
    except Exception as e:
        return _json_err("confirm_failed", str(e), {"request_id": request_id})

    try:
        kind = prop.kind
        payload = prop.payload or {}
        if kind == "transfer_eth":
            chain = payload["chain"]
            tx = payload["tx"]
            policy_engine.validate_transfer_native(
                chain=chain,
                to_address=payload.get("to_address", tx["to"]),
                amount=float(payload.get("amount", 0.0)),
                overrides=_effective_overrides(),
            )
            w3 = _get_web3(chain)
            signer = get_signer()
            signed = signer.sign_transaction(tx, chain_id=int(w3.eth.chain_id))
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            return _json_ok({"request_id": request_id, "kind": kind, "tx_hash": w3.to_hex(tx_hash)})

        if kind == "swap_tokens":
            chain = payload["chain"]
            tx = payload["tx"]
            w3 = _get_web3(chain)
            signer = get_signer()
            signed = signer.sign_transaction(tx, chain_id=int(w3.eth.chain_id))
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            return _json_ok({"request_id": request_id, "kind": kind, "tx_hash": w3.to_hex(tx_hash)})

        if kind == "place_cex_order":
            exchange = payload["exchange"]
            symbol = payload["symbol"]
            market_type = payload.get("market_type", "spot")
            side = payload["side"]
            amount = float(payload["amount"])
            order_type = payload["order_type"]
            price = payload.get("price")
            policy_engine.validate_cex_order(
                exchange_id=exchange,
                symbol=symbol,
                market_type=market_type,
                side=side,
                amount=amount,
                order_type=order_type,
                price=price,
                overrides=_effective_overrides(),
            )
            ex = CexExecutor(exchange_id=exchange, market_type=market_type)
            order = ex.place_order(symbol=symbol, side=side, amount=amount, order_type=order_type, price=price)
            return _json_ok({"request_id": request_id, "kind": kind, "order": ex.normalize_order(order)})

        return _json_err("unknown_kind", "Unknown execution kind.", {"request_id": request_id, "kind": kind})
    except PolicyError as e:
        return _json_err(e.code, e.message, e.data)
    except Exception as e:
        return _json_err("execution_failed", str(e), {"request_id": request_id, "kind": prop.kind})

if __name__ == "__main__":
    # This allows testing the server via `python server.py`
    mcp.run()

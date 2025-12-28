# ReadyTrader

## Important Disclaimer (Read Before Use)

ReadyTrader is provided for informational and educational purposes only and does not constitute financial, investment, legal, or tax advice. Trading digital assets involves substantial risk and may result in partial or total loss of funds. Past performance is not indicative of future results. You are solely responsible for any decisions, trades, configurations, supervision, and the security of your keys/credentials. ReadyTrader is provided “AS IS”, without warranties of any kind, and we make no guarantees regarding profitability, performance, availability, or outcomes. By using ReadyTrader, you acknowledge and accept these risks.

See also: `DISCLAIMER.md`.

---

**Turn your AI Agent into a Hedge Fund Manager.**

This MCP (Model Context Protocol) Server provides a complete suite of cryptocurrency trading tools for AI agents. It goes beyond simple buy/sell commands, offering a "Risk-Aware" and "Regime-Adaptive" architecture.

## 🚀 Key Features

*   **📉 Paper Trading Simulator**: Zero-risk practice environment with persistent balances and realistic order handling (Limit & Market).
*   **🧠 Strategy Factory**: Built-in Backtesting Engine. Agents can write Python strategies, run them against historical data, and get instant PnL feedback.
*   **🛡️ Risk Guardian**: Hard-coded safety layer. Automatically rejects trade requests that violate risk management rules (e.g., Position Sizing > 5%, "Falling Knife" protection).
*   **☀️ Market Regime Detection**: "Self-Awareness" of market conditions. Detects if the market is **Trending**, **Ranging (Chop)**, or **Volatile** using ADX/ATR.
*   **📰 Advanced Intelligence**: Institutional-grade simulated feeds for Social Sentiment (X/Reddit) and Financial News (Bloomberg/Reuters).

---

## 🛠️ Installation & Setup

### Prerequisites
*   Docker & Docker Compose

### 1. Build & Run (Standalone)
Run the server in a container. It exposes stdio for MCP clients.
```bash
cd ReadyTrader
docker build -t readytrader .
# Run interactively (to test)
docker run --rm -i readytrader
```

### 2. Configuration (`.env`)
Create a `.env` file or pass environment variables:
*   `PAPER_MODE=true` (Default: Safe simulation mode. Set `false` for real trading)
*   `PRIVATE_KEY=...` (Required ONLY if `PAPER_MODE=false`)

#### Live Trading Safety (Phase 0/1)
When `PAPER_MODE=false`, **live execution is still blocked by default** until you explicitly enable it and provide one-time consent (per container run).

*   `LIVE_TRADING_ENABLED=false` (Default. Must be `true` to allow live execution)
*   `TRADING_HALTED=false` (Kill switch. Set `true` to halt live trading immediately)
*   `EXECUTION_MODE=dex` (Options: `dex`, `cex`, `hybrid`)
*   **Execution approval mode** (user-selectable):
    - `EXECUTION_APPROVAL_MODE=auto` (default) executes trades immediately
    - `EXECUTION_APPROVAL_MODE=approve_each` returns proposals and requires `confirm_execution`\n
  Backward compatible: `HUMAN_CONFIRMATION=true` implies `EXECUTION_APPROVAL_MODE=approve_each`.

#### Optional Policy Controls (Phase 1)
These are **deny-by-policy only if set** (if unset, the policy engine is permissive).

*   `ALLOW_CHAINS=ethereum,base,arbitrum,optimism`
*   `ALLOW_TOKENS=usdc,weth,usdt,eth` (symbol allowlist; case-insensitive)
*   `ALLOW_ROUTERS=0xrouter1,0xrouter2` (DEX router/spender allowlist)
*   `MAX_TRADE_AMOUNT=1000` (max `amount` passed to `swap_tokens`)
*   `MAX_TRADE_AMOUNT_USDC=5000` (token-specific max)
*   `MAX_TRANSFER_NATIVE=0.1` (max native transfer amount)
*   `ALLOW_TO_ADDRESSES=0xabc...,0xdef...` (native transfer recipient allowlist)
*   `DEX_SLIPPAGE_PCT=1.0` (passed to the 1inch swap API builder)
*   `ALLOW_EXCHANGES=binance,kraken,coinbase` (CEX allowlist)
*   `ALLOW_CEX_SYMBOLS=btc/usdt,eth/usdt` (CEX symbol allowlist; case-insensitive)
*   `ALLOW_CEX_MARKET_TYPES=spot,swap,future` (CEX market-type allowlist; `swap` = perpetuals)
*   `MAX_CEX_ORDER_AMOUNT=0.05` (max base-asset amount per CEX order)

#### Market data connector tuning (CCXT) — competitive parity with CCXT MCP servers
These settings improve market-data reliability and performance via caching, proxy support, and market-type selection.

* `MARKETDATA_EXCHANGES=binance,kraken,coinbase,kucoin,bybit` (fallback order)
* `CCXT_DEFAULT_TYPE=spot` (or `future` / `swap`, exchange-dependent)
* `CCXT_PROXY=http://127.0.0.1:7890` (or use `HTTP_PROXY` / `HTTPS_PROXY`)
* `TICKER_CACHE_TTL_SEC=5`
* `OHLCV_CACHE_TTL_SEC=60`
* `MARKETS_CACHE_TTL_SEC=300`
* `HTTP_TIMEOUT_SEC=10` (used for external HTTP calls like 1inch API)

#### Phase 6: Rate limiting (in-memory)
These limits reset when the container restarts.
* `RATE_LIMIT_DEFAULT_PER_MIN=120`
* `RATE_LIMIT_EXECUTION_PER_MIN=20`
* Per-tool override: `RATE_LIMIT_SWAP_TOKENS_PER_MIN=5` (tool names are uppercased)

#### Phase 6: Two-step execution confirmation (optional)
If `HUMAN_CONFIRMATION=true`, live execution tools return a proposal with `request_id` + `confirm_token`.\n
Use:\n
* `list_pending_executions()`\n
* `confirm_execution(request_id, confirm_token)` (single-use, TTL)\n
* `cancel_execution(request_id)`\n

#### Phase 6: Advanced Risk Mode (urgent consent)
Advanced mode allows raising certain hard limits **at runtime** (in-memory only; resets on restart).\n
1) Call `get_advanced_risk_disclosure()`\n
2) Call `accept_advanced_risk_disclosure(true)`\n
3) Call `set_policy_overrides('{\"MAX_TRADE_AMOUNT\": 5000, \"MAX_CEX_ORDER_AMOUNT\": 1.0}')`\n
You can review with `get_policy_overrides()`.

#### Risk profiles (Phase C)
You can select a risk profile (per-process) to set reasonable default hard limits:
- `conservative` (default)
- `balanced`
- `aggressive` (requires Advanced Risk consent)

Use:
* `get_execution_preferences()`
* `set_execution_preferences(execution_approval_mode='auto', risk_profile='balanced')`

#### One-time (per run) risk disclosure consent
In live mode, the MCP will reject all execution tools until consent is granted:
1. Call `get_risk_disclosure()` to retrieve the disclosure text.
2. Call `accept_risk_disclosure(true)` once to enable live execution for **this process only**.
   - Consent resets every time the container restarts.

#### Signing configuration (Phase 2)
By default, live signing uses a raw private key from `PRIVATE_KEY` (development only). For better security, use an encrypted keystore.

* `SIGNER_TYPE=env_private_key` (default) or `SIGNER_TYPE=keystore`
* If `SIGNER_TYPE=env_private_key`: set `PRIVATE_KEY=...`
* If `SIGNER_TYPE=keystore`:
  - `KEYSTORE_PATH=/path/to/keystore.json`
  - `KEYSTORE_PASSWORD=...`

#### CEX credentials (Phase 3)
To place CEX orders or fetch CEX balances, configure ccxt credentials via env.

Generic (applies to the default exchange you pass to the tool):
* `CEX_API_KEY=...`
* `CEX_API_SECRET=...`
* `CEX_API_PASSWORD=...` (optional; some exchanges)

Or per-exchange (preferred):
* `CEX_BINANCE_API_KEY=...`
* `CEX_BINANCE_API_SECRET=...`
* `CEX_BINANCE_API_PASSWORD=...` (optional)

Tools:
* `place_cex_order(symbol, side, amount, order_type='market', price=None, exchange='binance', market_type='spot', idempotency_key='')`
* `get_cex_balance(exchange='binance', market_type='spot')`
* `get_cex_order(order_id, symbol='', exchange='binance', market_type='spot')`
* `cancel_cex_order(order_id, symbol='', exchange='binance', market_type='spot')`
* `get_cex_capabilities(exchange='binance', symbol='', market_type='spot')`

Market-data introspection:
* `get_marketdata_capabilities(exchange_id='')`

---

## 🔌 Integration Guide

### Option A: Agent Zero (Recommended)
To give Agent Zero these powers, add the following to your **Agent Zero Settings** (or `agent.yaml`):

**Via User Interface:**
1.  Go to **Settings** -> **MCP Servers**.
2.  Add a new server:
    *   **Name**: `readytrader`
    *   **Type**: `stdio`
    *   **Command**: `docker`
    *   **Args**: `run`, `-i`, `--rm`, `-e`, `PAPER_MODE=true`, `readytrader`

**Via `agent.yaml`:**
```yaml
mcp_servers:
  readytrader:
    command: "docker"
    args: 
      - "run"
      - "-i" 
      - "--rm"
      - "-e"
      - "PAPER_MODE=true"
      - "readytrader"
```
*Restart Agent Zero after saving.*

### Option B: Generic MCP Client (Claude Desktop, etc.)
Add this to your `mcp-server-config.json`:
```json
{
  "mcpServers": {
    "readytrader": {
      "command": "docker",
      "args": [
        "run", 
        "-i", 
        "--rm", 
        "-e", "PAPER_MODE=true", 
        "readytrader"
      ]
    }
  }
}
```

---

## 📚 Feature Guide

### 1. The Strategy Builder (Backtesting)
Your agent can "research" before it trades. Ask it to **develop and test** a strategy.

**Example Prompt:**
> "Create a mean-reversion strategy for BTC/USDT. Write a Python function `on_candle` that uses RSI. Run a backtest simulation on the last 500 hours and tell me the Win Rate and PnL."

**What happens:**
1.  Agent calls `fetch_ohlcv("BTC/USDT")` to see data structure.
2.  Agent writes code for `on_candle(close, rsi, state)`.
3.  Agent calls `run_backtest_simulation(code, "BTC/USDT")`.
4.  Server runs the code in a sandbox and returns `{ "pnl": 15.5%, "win_rate": 60% }`.

### 2. Paper Trading Laboratory
Perfect for "interning" your agent.
*   **Deposit Funds**: `deposit_paper_funds("USDC", 10000)`
*   **Place Orders**: `place_limit_order("buy", "ETH/USDT", 1.0, 2500.0)`
*   **Check Status**: `get_address_balance(..., "paper")`

### 3. Market Regime & Risk
The agent can query the "weather" before flying.
*   **Tool**: `get_market_regime("BTC/USDT")`
*   **Output**: `{"regime": "TRENDING", "direction": "UP", "adx": 45.2}`
*   **Agent Logic**: "The market is Trending Up (ADX > 25). I will switch to my Trend-Following Strategy and disable Mean-Reversion."

**The Guardian (Passive Safety):**
You don't need to do anything. If the agent tries to bet 50% of the portfolio on a whim, `validate_trade_risk` will **BLOCK** the trade automatically.

---

## 🧰 Tool Reference

| Category | Tool | Description |
| :--- | :--- | :--- |
| **Market Data** | `get_crypto_price` | Live price from CEX. |
| | `fetch_ohlcv` | Historical candles for research. |
| | `get_market_regime` | **Trend/Chop Detection** (Phase 6). |
| **Intelligence** | `get_sentiment` | Fear & Greed Index. |
| | `get_social_sentiment` | X/Reddit Analysis (Simulated). |
| | `get_financial_news` | Bloomberg/Reuters (Simulated). |
| **Trading** | `swap_tokens` | Execute market order swap. |
| | `place_limit_order` | **Limit Order** (Paper Mode). |
| | `check_orders` | Update Order Book (Paper Mode). |
| **Account** | `get_address_balance`| Check Wallet Balance. |
| | `deposit_paper_funds`| Get fake money (Paper Mode). |
| **Research** | `run_backtest_simulation` | **Run Strategy Backtest**. |
| **Research** | `run_synthetic_stress_test` | Run **synthetic black-swan stress test** with deterministic replay + recommendations. |

---
*Built for the Agentic Future.*

## 🧪 Synthetic Stress Testing (Phase 5)
This MCP includes a **100% randomized but deterministic-by-seed** synthetic market simulator. It can generate trending, ranging, volatile regimes and inject **black swan crashes** and **parabolic blow-off tops**.\n

### Tool: `run_synthetic_stress_test(strategy_code, config_json='{}')`
Returns JSON containing:
- **metrics summary** across scenarios
- **replay seeds** (master + per-scenario)
- **artifacts**: CSV scenario metrics, plus worst-case equity curve CSV + trades JSON
- **recommendations**: suggested parameter changes (and applies to `PARAMS` keys if present)

Example `config_json`:
```json
{
  \"master_seed\": 123,
  \"scenarios\": 200,
  \"length\": 500,
  \"timeframe\": \"1h\",
  \"initial_capital\": 10000,
  \"start_price\": 100,
  \"base_vol\": 0.01,
  \"black_swan_prob\": 0.02,
  \"parabolic_prob\": 0.02
}
```

# ReadyTrader-Crypto MCP Tool Catalog

This file describes the available tools in the `app/tools` directory.

> [!TIP]
> AI agents can use these tools to gather intelligence, assess risk, and execute trades.

## Safety & governance

| Tool Name | Description |
| :--- | :--- |
| [`get_risk_disclosure`](#get-risk-disclosure) | Returns the live trading risk disclosure and whether it has been accepted for this process. |
| [`accept_risk_disclosure`](#accept-risk-disclosure) | One-time per-process consent gate for live trading. Resets on restart (non-persistent). |
| [`get_advanced_risk_disclosure`](#get-advanced-risk-disclosure) | Returns the advanced risk disclosure for enabling elevated risk limits. |
| [`accept_advanced_risk_disclosure`](#accept-advanced-risk-disclosure) | One-time per-process consent gate for Advanced Risk Mode. |
| [`get_policy_overrides`](#get-policy-overrides) | Return current in-memory policy overrides (advanced mode only). |
| [`set_policy_overrides`](#set-policy-overrides) | Set in-memory policy overrides. Only allowed after Advanced Risk consent. |
| [`get_execution_preferences`](#get-execution-preferences) | Return execution preferences for the current process (non-persistent). |
| [`set_execution_preferences`](#set-execution-preferences) | Set per-process execution preferences (approval mode + optional risk profile preset). |
| [`list_pending_executions`](#list-pending-executions) | List pending execution proposals (only used when EXECUTION_APPROVAL_MODE=approve_each). |
| [`confirm_execution`](#confirm-execution) | Confirm a previously proposed execution. Replay protected (single-use, TTL). |
| [`cancel_execution`](#cancel-execution) | Cancel a pending execution proposal by request_id. |
| [`validate_trade_risk`](#validate-trade-risk) | [GUARDIAN] Validate if a trade is safe to execute. |

### `get_risk_disclosure`

**Signature:** `get_risk_disclosure()`

```text
Returns the live trading risk disclosure and whether it has been accepted for this process.
```

---

### `accept_risk_disclosure`

**Signature:** `accept_risk_disclosure(accepted)`

```text
One-time per-process consent gate for live trading. Resets on restart (non-persistent).
```

---

### `get_advanced_risk_disclosure`

**Signature:** `get_advanced_risk_disclosure()`

```text
Returns the advanced risk disclosure for enabling elevated risk limits.
```

---

### `accept_advanced_risk_disclosure`

**Signature:** `accept_advanced_risk_disclosure(accepted)`

```text
One-time per-process consent gate for Advanced Risk Mode.
Resets on restart (non-persistent).
```

---

### `get_policy_overrides`

**Signature:** `get_policy_overrides()`

```text
Return current in-memory policy overrides (advanced mode only).
```

---

### `set_policy_overrides`

**Signature:** `set_policy_overrides(config_json)`

```text
Set in-memory policy overrides. Only allowed after Advanced Risk consent.
Resets on restart.
```

---

### `get_execution_preferences`

**Signature:** `get_execution_preferences()`

```text
Return execution preferences for the current process (non-persistent).
```

---

### `set_execution_preferences`

**Signature:** `set_execution_preferences(execution_approval_mode, risk_profile='')`

```text
Set per-process execution preferences (approval mode + optional risk profile preset).
```

---

### `list_pending_executions`

**Signature:** `list_pending_executions()`

```text
List pending execution proposals (only used when EXECUTION_APPROVAL_MODE=approve_each).
```

---

### `confirm_execution`

**Signature:** `confirm_execution(request_id, confirm_token)`

```text
Confirm a previously proposed execution. Replay protected (single-use, TTL).
```

---

### `cancel_execution`

**Signature:** `cancel_execution(request_id)`

```text
Cancel a pending execution proposal by request_id.
```

---

### `validate_trade_risk`

**Signature:** `validate_trade_risk(side, symbol, amount_usd, portfolio_value)`

```text
[GUARDIAN] Validate if a trade is safe to execute.
Checks position sizing and sentiment alignment.
```

---

## Execution (DEX/CEX)

| Tool Name | Description |
| :--- | :--- |
| [`swap_tokens`](#swap-tokens) | Swap tokens on a DEX (paper mode or live; subject to consent, EXECUTION_MODE, and policy limits). |
| [`transfer_eth`](#transfer-eth) | Send ETH (or native token) to an address. |
| [`place_cex_order`](#place-cex-order) | Place a CEX order (paper mode simulates; live requires consent, EXECUTION_MODE, and policy limits). |
| [`get_cex_order`](#get-cex-order) | Fetch a live CEX order by id (read-only; requires CEX venue allowed; not supported in paper mode). |
| [`cancel_cex_order`](#cancel-cex-order) | Cancel a live CEX order (requires live-trading consent gates; not supported in paper mode). |
| [`wait_for_cex_order`](#wait-for-cex-order) | Poll an order until it reaches a terminal status or timeout expires. |
| [`get_cex_balance`](#get-cex-balance) | Fetch authenticated CEX balances (live only; respects CEX allowlists). |
| [`get_cex_capabilities`](#get-cex-capabilities) | Return CCXT capability metadata for a given exchange and optional symbol. |
| [`list_cex_open_orders`](#list-cex-open-orders) | List open orders on a CEX account (live only). |
| [`list_cex_orders`](#list-cex-orders) | List recent CEX orders (live only). |
| [`get_cex_my_trades`](#get-cex-my-trades) | List recent authenticated CEX trades (live only). |
| [`cancel_all_cex_orders`](#cancel-all-cex-orders) | Cancel all open orders on a CEX (live only; requires consent gates). |
| [`replace_cex_order`](#replace-cex-order) | Replace an existing CEX order (best-effort; exchange support varies; live only). |

### `swap_tokens`

**Signature:** `swap_tokens(from_token, to_token, amount, chain='ethereum', rationale='')`

```text
Swap tokens on a DEX (paper mode or live; subject to consent, EXECUTION_MODE, and policy limits).
```

---

### `transfer_eth`

**Signature:** `transfer_eth(to_address, amount, chain='ethereum')`

```text
Send ETH (or native token) to an address.
REQUIRES 'PRIVATE_KEY' env var to be set.

Args:
    to_address: Recipient hex address.
    amount: Amount to send in ETH.
    chain: The chain name ('ethereum', 'base', 'arbitrum', 'optimism').
    
Returns:
    Transaction hash or simulation result.
```

---

### `place_cex_order`

**Signature:** `place_cex_order(symbol, side, amount, order_type='market', price=None, exchange='binance', market_type='spot', idempotency_key='')`

```text
Place a CEX order (paper mode simulates; live requires consent, EXECUTION_MODE, and policy limits).
```

---

### `get_cex_order`

**Signature:** `get_cex_order(order_id, symbol='', exchange='binance', market_type='spot')`

```text
Fetch a live CEX order by id (read-only; requires CEX venue allowed; not supported in paper mode).
```

---

### `cancel_cex_order`

**Signature:** `cancel_cex_order(order_id, symbol='', exchange='binance', market_type='spot')`

```text
Cancel a live CEX order (requires live-trading consent gates; not supported in paper mode).
```

---

### `wait_for_cex_order`

**Signature:** `wait_for_cex_order(exchange, order_id, symbol='', market_type='spot', timeout_sec=30, poll_interval_sec=2.0)`

```text
Poll an order until it reaches a terminal status or timeout expires.

This is a pragmatic alternative to private websocket order streams and is useful for agents that
want a single call to “wait for fill/cancel”.
```

---

### `get_cex_balance`

**Signature:** `get_cex_balance(exchange='binance', market_type='spot')`

```text
Fetch authenticated CEX balances (live only; respects CEX allowlists).
```

---

### `get_cex_capabilities`

**Signature:** `get_cex_capabilities(exchange='binance', symbol='', market_type='spot')`

```text
Return CCXT capability metadata for a given exchange and optional symbol.
```

---

### `list_cex_open_orders`

**Signature:** `list_cex_open_orders(exchange='binance', symbol='', market_type='spot', limit=100)`

```text
List open orders on a CEX account (live only).
```

---

### `list_cex_orders`

**Signature:** `list_cex_orders(exchange='binance', symbol='', market_type='spot', limit=100)`

```text
List recent CEX orders (live only).
```

---

### `get_cex_my_trades`

**Signature:** `get_cex_my_trades(exchange='binance', symbol='', market_type='spot', limit=100)`

```text
List recent authenticated CEX trades (live only).
```

---

### `cancel_all_cex_orders`

**Signature:** `cancel_all_cex_orders(exchange='binance', symbol='', market_type='spot')`

```text
Cancel all open orders on a CEX (live only; requires consent gates).
```

---

### `replace_cex_order`

**Signature:** `replace_cex_order(exchange, order_id, symbol, side, amount, order_type='limit', price=None, market_type='spot')`

```text
Replace an existing CEX order (best-effort; exchange support varies; live only).
```

---

## Paper trading

| Tool Name | Description |
| :--- | :--- |
| [`deposit_paper_funds`](#deposit-paper-funds) | [PAPER MODE] Deposit fake funds into the paper trading wallet. |
| [`reset_paper_wallet`](#reset-paper-wallet) | [PAPER MODE] Clear all balances and trade history to start fresh. |
| [`place_limit_order`](#place-limit-order) | Place a Limit Order to buy/sell at a specific price. |
| [`check_orders`](#check-orders) | [PAPER MODE] Check if any open limit orders should be filled based on current market price. |
| [`get_address_balance`](#get-address-balance) | Get the native coin balance of an address on a specific EVM chain. |

### `deposit_paper_funds`

**Signature:** `deposit_paper_funds(asset, amount)`

```text
[PAPER MODE] Deposit fake funds into the paper trading wallet.
```

---

### `reset_paper_wallet`

**Signature:** `reset_paper_wallet()`

```text
[PAPER MODE] Clear all balances and trade history to start fresh.
```

---

### `place_limit_order`

**Signature:** `place_limit_order(side, symbol, amount, price)`

```text
Place a Limit Order to buy/sell at a specific price.
Currently supported in PAPER MODE only.
```

---

### `check_orders`

**Signature:** `check_orders(symbol)`

```text
[PAPER MODE] Check if any open limit orders should be filled based on current market price.
Triggers a fill if conditions are met.
```

---

### `get_address_balance`

**Signature:** `get_address_balance(address, chain='ethereum')`

```text
Get the native coin balance of an address on a specific EVM chain.

Args:
    address: The hex address to check (e.g., '0x123...').
    chain: The chain name ('ethereum', 'base', 'arbitrum', 'optimism').
    
Returns:
    A string message with the balance in ETH (or native token).
```

---

## Market data

| Tool Name | Description |
| :--- | :--- |
| [`get_crypto_price`](#get-crypto-price) | Get the current price of a cryptocurrency. |
| [`get_multiple_prices`](#get-multiple-prices) | Get the current prices for multiple cryptocurrencies in a single call. |
| [`get_ticker`](#get-ticker) | Return the best available ticker for a symbol using the MarketDataBus. |
| [`fetch_ohlcv`](#fetch-ohlcv) | Fetch historical OHLCV data. |
| [`get_market_regime`](#get-market-regime) | Detect the current market regime (TRENDING, RANGING, VOLATILE). |
| [`get_marketdata_capabilities`](#get-marketdata-capabilities) | Return CCXT market data capabilities for a configured exchange (or primary). |
| [`get_marketdata_status`](#get-marketdata-status) | Return MarketDataBus/provider status and websocket/private stream health. |
| [`ingest_ticker`](#ingest-ticker) | Ingest an external ticker snapshot into the in-memory store. |
| [`ingest_ohlcv`](#ingest-ohlcv) | Ingest OHLCV into the in-memory store. |

### `get_crypto_price`

**Signature:** `get_crypto_price(symbol, exchange='binance')`

```text
Get the current price of a cryptocurrency.

Args:
    symbol: The trading pair symbol (e.g., 'BTC/USDT', 'ETH/USDT').
    exchange: The exchange to check (default: 'binance').
    
Returns:
    A string message with the price or an error.
```

---

### `get_multiple_prices`

**Signature:** `get_multiple_prices(symbols_json)`

```text
Get the current prices for multiple cryptocurrencies in a single call.

Args:
    symbols_json: A JSON array of trading pair symbols, e.g., '["BTC/USDT", "ETH/USDT"]'.
    
Returns:
    JSON object containing prices for all successfully fetched symbols.
```

---

### `get_ticker`

**Signature:** `get_ticker(symbol)`

```text
Return the best available ticker for a symbol using the MarketDataBus.
```

---

### `fetch_ohlcv`

**Signature:** `fetch_ohlcv(symbol, timeframe='1h', limit=24)`

```text
Fetch historical OHLCV data. 
Use this to analyze markets before Backtesting.
Returns a summarized string of the dataframe.
```

---

### `get_market_regime`

**Signature:** `get_market_regime(symbol, timeframe='1d')`

```text
Detect the current market regime (TRENDING, RANGING, VOLATILE).
Uses ADX and ATR indicators on historical data.
```

---

### `get_marketdata_capabilities`

**Signature:** `get_marketdata_capabilities(exchange_id='')`

```text
Return CCXT market data capabilities for a configured exchange (or primary).
```

---

### `get_marketdata_status`

**Signature:** `get_marketdata_status()`

```text
Return MarketDataBus/provider status and websocket/private stream health.
```

---

### `ingest_ticker`

**Signature:** `ingest_ticker(symbol, last, bid=None, ask=None, timestamp_ms=None, source='user', ttl_sec=10.0)`

```text
Ingest an external ticker snapshot into the in-memory store.

This enables “bring your own data feed”: an agent can fetch market data elsewhere (or via another MCP)
and push it into ReadyTrader-Crypto for use in paper simulation and price lookups.
```

---

### `ingest_ohlcv`

**Signature:** `ingest_ohlcv(symbol, timeframe, ohlcv_json, limit=100, source='user', ttl_sec=60.0)`

```text
Ingest OHLCV into the in-memory store.

`ohlcv_json` should be a JSON-encoded list of candles in CCXT format:
[[timestamp_ms, open, high, low, close, volume], ...]
```

---

## Websockets (Phase 2.5)

| Tool Name | Description |
| :--- | :--- |
| [`start_marketdata_ws`](#start-marketdata-ws) | Start a background websocket ticker stream for a top exchange. |
| [`stop_marketdata_ws`](#stop-marketdata-ws) | Stop a previously started public websocket ticker stream (Phase 2.5). |
| [`start_cex_private_ws`](#start-cex-private-ws) | Start an optional private order update websocket stream. |
| [`stop_cex_private_ws`](#stop-cex-private-ws) | Stop an optional private order updates stream (ws for binance; poll fallback otherwise). |
| [`list_cex_private_updates`](#list-cex-private-updates) | List recent private update events (best-effort, in-memory, bounded history). |

### `start_marketdata_ws`

**Signature:** `start_marketdata_ws(exchange, symbols_json, market_type='spot')`

```text
Start a background websocket ticker stream for a top exchange.

Supported exchanges: binance, coinbase, kraken
```

---

### `stop_marketdata_ws`

**Signature:** `stop_marketdata_ws(exchange, market_type='spot')`

```text
Stop a previously started public websocket ticker stream (Phase 2.5).
```

---

### `start_cex_private_ws`

**Signature:** `start_cex_private_ws(exchange='binance', market_type='spot')`

```text
Start an optional private order update websocket stream.

Implementation notes:
- binance uses a websocket user stream (spot + swap)
- other exchanges use an opt-in polling fallback (Phase 2) since CCXT Pro is not used here
```

---

### `stop_cex_private_ws`

**Signature:** `stop_cex_private_ws(exchange='binance', market_type='spot')`

```text
Stop an optional private order updates stream (ws for binance; poll fallback otherwise).
```

---

### `list_cex_private_updates`

**Signature:** `list_cex_private_updates(exchange='binance', market_type='spot', limit=100)`

```text
List recent private update events (best-effort, in-memory, bounded history).
```

---

## Research & evaluation

| Tool Name | Description |
| :--- | :--- |
| [`run_backtest_simulation`](#run-backtest-simulation) | Run a strategy simulation against historical data. |
| [`run_synthetic_stress_test`](#run-synthetic-stress-test) | Run a deterministic synthetic market stress test against strategy_code. |
| [`analyze_performance`](#analyze-performance) | Review past trade performance and generated lessons (optionally filtered by symbol). |

### `run_backtest_simulation`

**Signature:** `run_backtest_simulation(strategy_code, symbol, timeframe='1h')`

```text
Run a strategy simulation against historical data.

Args:
    strategy_code: Python code defining 'def on_candle(close, rsi, state): -> str'.
                   Must return 'buy', 'sell', or 'hold'.
    symbol: Trading pair (e.g. BTC/USDT).
    timeframe: Candle size (e.g. 1h, 4h, 1d).
    
Returns:
    JSON string containing PnL, Win Rate, and trade log.
```

---

### `run_synthetic_stress_test`

**Signature:** `run_synthetic_stress_test(strategy_code, config_json='{}')`

```text
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
```

---

### `analyze_performance`

**Signature:** `analyze_performance(symbol=None)`

```text
Review past trade performance and generated lessons (optionally filtered by symbol).
```

---

## Intelligence feeds

| Tool Name | Description |
| :--- | :--- |
| [`get_sentiment`](#get-sentiment) | Get the current Crypto Fear & Greed Index. |
| [`get_news`](#get-news) | Get aggregated crypto market news. |
| [`get_social_sentiment`](#get-social-sentiment) | Get simulated social media sentiment (X/Reddit). |
| [`get_financial_news`](#get-financial-news) | Get simulated high-tier financial news (Bloomberg/Reuters). |

### `get_sentiment`

**Signature:** `get_sentiment()`

```text
Get the current Crypto Fear & Greed Index.
```

---

### `get_news`

**Signature:** `get_news()`

```text
Get aggregated crypto market news.
```

---

### `get_social_sentiment`

**Signature:** `get_social_sentiment(symbol)`

```text
Get simulated social media sentiment (X/Reddit).
Returns a sentiment score and trending topics.
```

---

### `get_financial_news`

**Signature:** `get_financial_news(symbol)`

```text
Get simulated high-tier financial news (Bloomberg/Reuters).
```

---

## Ops / observability

| Tool Name | Description |
| :--- | :--- |
| [`get_health`](#get-health) | Lightweight health/readiness probe for operators. |
| [`get_metrics_snapshot`](#get-metrics-snapshot) | Return in-memory counters and timer aggregates. |

### `get_health`

**Signature:** `get_health()`

```text
Lightweight health/readiness probe for operators.
```

---

### `get_metrics_snapshot`

**Signature:** `get_metrics_snapshot()`

```text
Return in-memory counters and timer aggregates.
This is the Docker-first default: no extra ports required.
```

---

## Misc

| Tool Name | Description |
| :--- | :--- |
| [`get_capabilities`](#get-capabilities) | Describe supported venues, chains, and safety flags for MCP clients. |

### `get_capabilities`

**Signature:** `get_capabilities()`

```text
Describe supported venues, chains, and safety flags for MCP clients.
```

---

## Uncategorized

| Tool Name | Description |
| :--- | :--- |
| [`get_metrics_prometheus`](#get-metrics-prometheus) | Return metrics in Prometheus text exposition format (no HTTP server; Docker-first). |

### `get_metrics_prometheus`

**Signature:** `get_metrics_prometheus()`

```text
Return metrics in Prometheus text exposition format (no HTTP server; Docker-first).
```

---

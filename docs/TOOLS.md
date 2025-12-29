## ReadyTrader MCP Tool Catalog

This file is generated from `server.py`.

Regenerate with:

```bash
python tools/generate_tool_docs.py
```

### Safety & governance

- **`get_risk_disclosure()`**
  - Returns the live trading risk disclosure and whether it has been accepted for this process.

- **`accept_risk_disclosure(accepted)`**
  - One-time per-process consent gate for live trading. Resets on restart (non-persistent).

- **`get_advanced_risk_disclosure()`**
  - Returns the advanced risk disclosure for enabling elevated risk limits.

- **`accept_advanced_risk_disclosure(accepted)`**
  - One-time per-process consent gate for Advanced Risk Mode.

- **`get_policy_overrides()`**
  - Return current in-memory policy overrides (advanced mode only).

- **`set_policy_overrides(config_json)`**
  - Set in-memory policy overrides. Only allowed after Advanced Risk consent.

- **`get_execution_preferences()`**
  - Return execution preferences for the current process (non-persistent).

- **`set_execution_preferences(execution_approval_mode, risk_profile='')`**
  - Set per-process execution preferences (approval mode + optional risk profile preset).

- **`list_pending_executions()`**
  - List pending execution proposals (only used when EXECUTION_APPROVAL_MODE=approve_each).

- **`confirm_execution(request_id, confirm_token)`**
  - Confirm a previously proposed execution. Replay protected (single-use, TTL).

- **`cancel_execution(request_id)`**
  - Cancel a pending execution proposal by request_id.

- **`validate_trade_risk(side, symbol, amount_usd, portfolio_value)`**
  - [GUARDIAN] Validate if a trade is safe to execute.

### Execution (DEX/CEX)

- **`swap_tokens(from_token, to_token, amount, chain='ethereum', rationale='')`**
  - Swap tokens on a DEX (paper mode or live; subject to consent, EXECUTION_MODE, and policy limits).

- **`transfer_eth(to_address, amount, chain='ethereum')`**
  - Send ETH (or native token) to an address.

- **`place_cex_order(symbol, side, amount, order_type='market', price=None, exchange='binance', market_type='spot', idempotency_key='')`**
  - Place a CEX order (paper mode simulates; live requires consent, EXECUTION_MODE, and policy limits).

- **`get_cex_order(order_id, symbol='', exchange='binance', market_type='spot')`**
  - Fetch a live CEX order by id (read-only; requires CEX venue allowed; not supported in paper mode).

- **`cancel_cex_order(order_id, symbol='', exchange='binance', market_type='spot')`**
  - Cancel a live CEX order (requires live-trading consent gates; not supported in paper mode).

- **`wait_for_cex_order(exchange, order_id, symbol='', market_type='spot', timeout_sec=30, poll_interval_sec=2.0)`**
  - Poll an order until it reaches a terminal status or timeout expires.

- **`get_cex_balance(exchange='binance', market_type='spot')`**
  - Fetch authenticated CEX balances (live only; respects CEX allowlists).

- **`get_cex_capabilities(exchange='binance', symbol='', market_type='spot')`**
  - Return CCXT capability metadata for a given exchange and optional symbol.

- **`list_cex_open_orders(exchange='binance', symbol='', market_type='spot', limit=100)`**
  - List open orders on a CEX account (live only).

- **`list_cex_orders(exchange='binance', symbol='', market_type='spot', limit=100)`**
  - List recent CEX orders (live only).

- **`get_cex_my_trades(exchange='binance', symbol='', market_type='spot', limit=100)`**
  - List recent authenticated CEX trades (live only).

- **`cancel_all_cex_orders(exchange='binance', symbol='', market_type='spot')`**
  - Cancel all open orders on a CEX (live only; requires consent gates).

- **`replace_cex_order(exchange, order_id, symbol, side, amount, order_type='limit', price=None, market_type='spot')`**
  - Replace an existing CEX order (best-effort; exchange support varies; live only).

### Paper trading

- **`deposit_paper_funds(asset, amount)`**
  - [PAPER MODE] Deposit fake funds into the paper trading wallet.

- **`place_limit_order(side, symbol, amount, price)`**
  - Place a Limit Order to buy/sell at a specific price.

- **`check_orders(symbol)`**
  - [PAPER MODE] Check if any open limit orders should be filled based on current market price.

- **`get_address_balance(address, chain='ethereum')`**
  - Get the native coin balance of an address on a specific EVM chain.

### Market data

- **`get_crypto_price(symbol, exchange='binance')`**
  - Get the current price of a cryptocurrency.

- **`get_ticker(symbol)`**
  - Return the best available ticker for a symbol using the MarketDataBus.

- **`fetch_ohlcv(symbol, timeframe='1h', limit=24)`**
  - Fetch historical OHLCV data.

- **`get_market_regime(symbol, timeframe='1d')`**
  - Detect the current market regime (TRENDING, RANGING, VOLATILE).

- **`get_marketdata_capabilities(exchange_id='')`**
  - Return CCXT market data capabilities for a configured exchange (or primary).

- **`get_marketdata_status()`**
  - Return MarketDataBus/provider status and websocket/private stream health.

- **`ingest_ticker(symbol, last, bid=None, ask=None, timestamp_ms=None, source='user', ttl_sec=10.0)`**
  - Ingest an external ticker snapshot into the in-memory store.

- **`ingest_ohlcv(symbol, timeframe, ohlcv_json, limit=100, source='user', ttl_sec=60.0)`**
  - Ingest OHLCV into the in-memory store.

### Websockets (Phase 2.5)

- **`start_marketdata_ws(exchange, symbols_json, market_type='spot')`**
  - Start a background websocket ticker stream for a top exchange.

- **`stop_marketdata_ws(exchange, market_type='spot')`**
  - Stop a previously started public websocket ticker stream (Phase 2.5).

- **`start_cex_private_ws(exchange='binance', market_type='spot')`**
  - Start an optional private order update websocket stream.

- **`stop_cex_private_ws(exchange='binance', market_type='spot')`**
  - Stop an optional private order update websocket stream (Phase 2.5).

- **`list_cex_private_updates(exchange='binance', market_type='spot', limit=100)`**
  - List recent private websocket events (best-effort, in-memory, bounded history).

### Research & evaluation

- **`run_backtest_simulation(strategy_code, symbol, timeframe='1h')`**
  - Run a strategy simulation against historical data.

- **`run_synthetic_stress_test(strategy_code, config_json='{}')`**
  - Run a deterministic synthetic market stress test against strategy_code.

- **`analyze_performance(symbol=None)`**
  - Review past trade performance and generated lessons (optionally filtered by symbol).

### Intelligence feeds

- **`get_sentiment()`**
  - Get the current Crypto Fear & Greed Index.

- **`get_news()`**
  - Get aggregated crypto market news.

- **`get_social_sentiment(symbol)`**
  - Get simulated social media sentiment (X/Reddit).

- **`get_financial_news(symbol)`**
  - Get simulated high-tier financial news (Bloomberg/Reuters).

### Ops / observability

- **`get_health()`**
  - Lightweight health/readiness probe for operators.

- **`get_metrics_snapshot()`**
  - Return in-memory counters and timer aggregates.

### Misc

- **`get_capabilities()`**
  - Describe supported venues, chains, and safety flags for MCP clients.

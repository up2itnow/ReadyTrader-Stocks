# Market Data Architecture (ReadyTrader-Stocks)

ReadyTrader-Stocks routes market data via `MarketDataBus` and exposes it through MCP tools like `get_stock_price()` and `fetch_ohlcv()`.

## 📡 Data Providers
The system wires providers in this order of priority:

1.  **Ingest Provider**: Manually pushed data from other agents or tools.
2.  **WebSocket Provider**: Real-time streaming data from **Alpaca** (if configured).
3.  **Stock Provider (Fallback)**: REST-based data from **yfinance** or brokerage APIs.

## ⚡ WebSocket Streams
WebSocket streaming is **opt-in**. To enable it for a ticker, the agent calls `start_marketdata_ws`.

- **Source**: Alpaca real-time quotes (IEX/SIP).
- **Format**: Unified snapshot format containing `symbol`, `bid`, `ask`, and `last`.

## 📦 Persistence
Market data is kept in-memory with short TTLs (default 5-60 seconds) to ensure agents never trade on stale prices. If you need historical data for backtesting, use `fetch_ohlcv`.

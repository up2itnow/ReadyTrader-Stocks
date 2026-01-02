## ReadyTrader-Stocks — Brokerage Capabilities

This is a **truthful capability matrix** for stock brokerages. “Supported” means we have a clear tool path, tests, and documented behavior. “Experimental” means it may work, but behavior varies.

### Legend
- **Supported**: expected to work reliably; covered by unit tests where possible.
- **Experimental**: best-effort; brokerage-specific quirks likely.
- **N/A**: not implemented.

### Public market data
ReadyTrader-Stocks can fetch public data via:
- **yfinance** (Standard fallback for historical and real-time quotes)
- **Alpaca REST** (Configured via `ALPACA_API_KEY`)
- **Alpaca WebSocket Tickers (opt-in)**: Real-time quotes via IEX/SIP (see `start_marketdata_ws`)

### Private account/order updates
ReadyTrader-Stocks supports:
- **Brokerage Polling** for all supported providers: periodically fetch open orders and portfolio status.
- **Alpaca Events (Future)**: Real-time trade/order updates.

---

## Capability matrix (high level)

| Brokerage | Market Orders | Limit Orders | Streaming Data | Paper Trading | Notes |
|-----------|--------------|--------------|----------------|---------------|-------|
| **Alpaca** | Supported | Supported | Supported (WS) | Supported | Recommended for paper trading |
| **Tradier** | Supported | Supported | N/A (REST only) | N/A | OAuth required |
| **Schwab** | Experimental | Experimental | N/A | N/A | Bearer token required |
| **E*TRADE** | Experimental | Experimental | N/A | N/A | OAuth1 |
| **Robinhood** | Experimental | Experimental | N/A | N/A | MFA complications |

---

## Tool coverage (Brokerage)

### Core execution
- `place_stock_order(...)`: Supported (Alpaca, Tradier)
- `cancel_order(...)`: Supported
- `get_order(...)`: Supported (Polling fallback)

### Account and portfolio
- `get_portfolio_balance()`: Supported
- `list_positions()`: Supported
- `reset_paper_wallet()`: Supported (Paper mode only)

---

## Operator notes

### Polling frequency
For brokerages without real-time event support:
- `BROKERAGE_POLL_INTERVAL_SEC` (default 2.0 seconds) is used to refresh local state.
- Polling is subject to rate limits; use sparingly.

## Changelog

This project follows a lightweight changelog format.

### Unreleased
- **Stock Focus Transition**: Completed full refactor from crypto-focused connections to stock brokerage architecture.
- **WebSocket Streams**: Replaced crypto streams (Binance/Coinbase/Kraken) with Alpaca stock streaming.
- **Execution Routing**: Updated router terminology to focus on stock brokerages and retail execution.
- **Tool Catalog**: Cleaned up MCP tools to remove crypto-specific actions (`swap_tokens`, `get_crypto_price`, etc.).
- **Documentation**: Fully rebranded all docs from ReadyTrader-Stocks to ReadyTrader-Stocks.

### 0.1.0 (2025-12-29)
- **Initial Release (Crypto Focus)**: Agent-first MCP server for crypto trading workflows.
- **Safety governance**: risk disclosure, kill switch, approve-each execution.
- **Execution**: CEX via CCXT + DEX swaps.
- **Stress lab**: deterministic synthetic stress testing.

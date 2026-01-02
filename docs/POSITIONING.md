## ReadyTrader-Stocks Positioning

### What ReadyTrader-Stocks is (credible one-liner)
**ReadyTrader-Stocks is a safety-governed stock trading MCP server** that lets LLM agents (Agent Zero, Claude, etc.) research, paper trade, and (optionally) execute live trades via brokerage connectors with built-in risk disclosures, policy limits, and operator controls.

---

## Messaging pillars

### 1) Safety-first automation
- **Paper mode default** (`PAPER_MODE=true`)
- **Live trading opt-in** (`LIVE_TRADING_ENABLED=true` + consent)
- **Kill switch** (`TRADING_HALTED=true`)
- **Approval mode** (`approve_each`)
- **Central policy engine** (allowlists/limits)

### 2) Agent-first UX
Tools return **structured JSON** with stable error codes, making it easier for agents to plan and recover.

### 3) Research & robustness
Built-in workflows for disciplined operators:
- backtesting
- synthetic stress testing
- market regime signals

### 4) Composable market data
- `yfinance` fallback
- `alpaca` websocket-first public streams (opt-in)
- user-ingested snapshots

---

## Differentiation

### vs “Simple Stock APIs”
ReadyTrader-Stocks adds:
- trade governance (consent + kill switch)
- policy limits
- synthetic stress lab
- agent-friendly structured outputs

---

## Recommended positioning copy

### Homepage-style blurb
ReadyTrader-Stocks turns your MCP-capable AI agent into a **risk-aware trading operator**: research + paper trade + optional live execution through brokerage connectors with explicit consent gates, policy limits, and operator controls.

---

## Target audiences

### AI Developers
- “structured JSON outputs”
- “consistent error taxonomy”
- “execution routing: brokerage-first”

### Retail Traders
- “policy engine allowlists/limits”
- “kill switch”
- “paper trading by default”

# ReadyTrader-Stocks Threat Model

This document is an operator-focused threat model for ReadyTrader-Stocks when configured for **live trading** (`PAPER_MODE=false`).

## 🌟 Security Philosophy
ReadyTrader-Stocks is a **Safety-First Bridge**. It is designed to minimize "fat finger" errors and limit the damage a compromised AI agent (or logic error) can do.

---

## 🚫 1. Brokerage API Key Compromise
- **Threat**: An attacker gains access to your `.env` file containing `ALPACA_API_KEY` or `TRADIER_ACCESS_TOKEN`.
- **Mitigation**:
    - Use environment-specific keys with restricted permissions (e.g., Trading only, no Withdrawals).
    - Enable **Risk Guardian** limits (e.g., `MAX_ORDER_AMOUNT`) in `core/policy.py`.
    - Run ReadyTrader-Stocks in a secured container or isolated environment.

## 🚫 2. Rogue Agent / "Fat Finger" Trades
- **Threat**: The AI agent attempts to buy a massive amount of a volatile stock or enters a trade with an incorrect price.
- **Mitigation**:
    - **Execution Approval Mode**: Set `EXECUTION_APPROVAL_MODE=approve_each` to require manual human confirmation for every trade.
    - **Price Collars**: Built-in 5% price deviation check in `RiskGuardian.validate_trade`.
    - **Pattern Day Trader (PDT) Guards**: Policy limits to prevent account flagging.

## 🚫 3. Prompt Injection / Social Engineering
- **Threat**: A user convinces the AI agent to bypass safety rules or sell positions maliciously.
- **Mitigation**:
    - The **Risk Guardian** is hard-coded in Python and cannot be bypassed by prompt-level instructions.
    - All trades must pass the `validate_trade_risk` tool which enforces global limits.

---

## 🔒 Best Practices
1.  **Never** reuse API keys across multiple apps.
2.  **Enable MFA** on your brokerage account for any manual actions.
3.  **Audit Logs**: Regularly review the `audit.log` for unexpected trade payloads.
4.  **Paper First**: Always run a strategy in `PAPER_MODE=true` for at least 48 hours before enabling live trading.

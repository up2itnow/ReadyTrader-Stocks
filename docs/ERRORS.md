# Error Catalog & Troubleshooting

This document helps operators diagnose common issues when running ReadyTrader-Stocks.

| Issue | Potential Fix |
| :--- | :--- |
| **Missing .env** | Run `python tools/setup_wizard.py` to generate one. |
| **Missing Keys** | Check `docs/SENTIMENT.md` for API key instructions. |
| **Blocked Trade** | The trade may have exceeded your `MAX_ORDER_AMOUNT` or violated a price collar. |
| **Dependency Error** | Run `pip install -r requirements.txt` to ensure all libraries are present. |

---

## 🤖 Error Codes (Operator Guide)

### Risk & Compliance
- `risk_blocked`: The Risk Guardian rejected the trade due to size, sentiment, or drawdown limits.
- `pdt_violation`: Pattern Day Trader protection triggered for an account under $25k.
- `price_collar_violation`: Price is too far (>5%) from the last known close.

### Execution
- `brokerage_not_configured`: You are attempting a live trade but no API keys were found.
- `brokerage_not_supported`: The requested brokerage is not yet integrated.
- `insufficient_funds`: (Paper Mode) Your virtual balance is too low for the requested trade.

### Market Data
- `ticker_not_found`: The requested symbol is invalid or data is unavailable.
- `rate_limited`: You have exceeded the API limits for your data provider.

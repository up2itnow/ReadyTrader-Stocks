### 🚨 Quick Fix Troubleshooting

If you are just getting started and seeing errors, check these first:

| Issue | Quick Fix | Reference |
| :--- | :--- | :--- |
| **Missing .env** | Run `python tools/setup_wizard.py` to generate one. | [Setup Wizard](file:///Users/billwilson_home/Desktop/ReadyTrader-Crypto/tools/setup_wizard.py) |
| **Missing Keys** | Check `docs/SENTIMENT.md` for links to get free API keys. | [Sentiment Guide](file:///Users/billwilson_home/Desktop/ReadyTrader-Crypto/docs/SENTIMENT.md) |
| **Blocked Trade** | Your trade might violate the `RISK_PROFILE`. Use `conservative` for safety. | [README.md](file:///Users/billwilson_home/Desktop/ReadyTrader-Crypto/README.md) |
| **Python Errors** | Run `pip install -r requirements.txt` to ensure dependencies are met. | [requirements.txt](file:///Users/billwilson_home/Desktop/ReadyTrader-Crypto/requirements.txt) |

---

### ReadyTrader-Crypto Error Codes (Operator Guide)

### Live trading governance
- **`live_trading_disabled`**
  - Meaning: Live execution is blocked because `LIVE_TRADING_ENABLED` is not `true`.
  - Fix: set `LIVE_TRADING_ENABLED=true` (and restart if running in Docker with env vars baked in).
- **`trading_halted`**
  - Meaning: Kill switch is on (`TRADING_HALTED=true`).
  - Fix: set `TRADING_HALTED=false` to resume, or keep it enabled to stop all live execution.
- **`consent_required`**
  - Meaning: Per-process risk disclosure has not been accepted for this run.
  - Fix: call `get_risk_disclosure()`, then `accept_risk_disclosure(true)`.
- **`advanced_consent_required`**
  - Meaning: Advanced Risk Mode overrides are blocked until urgent consent is accepted.
  - Fix: call `get_advanced_risk_disclosure()`, then `accept_advanced_risk_disclosure(true)`.

### Execution routing
- **`execution_mode_blocked`**
  - Meaning: The requested tool is blocked by `EXECUTION_MODE` (dex/cex/hybrid).
  - Fix: set `EXECUTION_MODE` to allow the venue you want, or use the corresponding venue tool.

### Rate limiting
- **`rate_limited`**
  - Meaning: The per-tool (or default) rate limit was exceeded for the current 60s window.
  - Fix:
    - slow down or batch calls
    - raise limits with `RATE_LIMIT_DEFAULT_PER_MIN`, `RATE_LIMIT_EXECUTION_PER_MIN`, or `RATE_LIMIT_<TOOL>_PER_MIN`

### Policy engine (allowlists / limits)
Common examples (non-exhaustive):
- **`chain_not_allowed`**, **`token_not_allowed`**, **`router_not_allowed`**
  - Meaning: Allowlist is set and the requested chain/token/router is not allowed.
  - Fix: update `ALLOW_CHAINS`, `ALLOW_TOKENS`, `ALLOW_ROUTERS` (or chain-specific `ALLOW_ROUTERS_<CHAIN>`).
- **`trade_amount_too_large`**, **`transfer_amount_too_large`**, **`order_amount_too_large`**
  - Meaning: A configured max limit was exceeded.
  - Fix: lower sizing, or (if appropriate) enable Advanced Risk Mode and adjust overrides/limits.

### Risk guardian (paper mode)
- **`risk_blocked`**
  - Meaning: Paper-mode risk checks blocked the trade (e.g., too large relative to portfolio).
  - Fix: reduce size, deposit more paper funds, or adjust the strategy parameters.
- **`risk_calc_error`**
  - Meaning: Paper-mode risk calculations failed; ReadyTrader-Crypto fails closed (safer).
  - Fix: check paper DB health, ensure prices/metrics can be computed, rerun.

### Websocket streams (Phase 2.5)
- **`ws_start_error`**, **`ws_stop_error`**
  - Meaning: Public websocket stream failed to start/stop (invalid symbols, network, etc.).
  - Fix: verify exchange name, symbol formats, and network access.
- **`private_ws_start_error`**, **`private_ws_stop_error`**, **`private_ws_list_error`**
  - Meaning: Private stream failed (credentials, exchange support, network).
  - Fix: verify CEX credentials and that the exchange supports the requested market type.

### CCXT / exchange connectivity
Errors are normalized via `errors.py` where possible:
- **`ccxt_auth_error`**, **`ccxt_permission_denied`**
  - Fix: check API keys, permissions, and allowlists.
- **`ccxt_rate_limited`**
  - Fix: reduce request frequency and/or tune caching and provider settings.
- **`ccxt_network_error`**, **`ccxt_exchange_unavailable`**
  - Fix: temporary outage; retry with backoff; consider switching marketdata providers.



### Market data guardrails (Phase 3)
- **`marketdata_not_acceptable`**
  - Meaning: Operator enabled fail-closed market data mode and the best available ticker was stale or flagged as an outlier.
  - Fix:
    - inspect `get_ticker(symbol)` → `meta.candidates` to see which sources are stale or failing
    - start/verify websocket streams (`start_marketdata_ws`) or ingest a feed (`ingest_ticker`)
    - tune thresholds: `MARKETDATA_MAX_AGE_MS*`, `MARKETDATA_OUTLIER_MAX_PCT`, `MARKETDATA_OUTLIER_WINDOW_MS`
    - disable fail-closed: `MARKETDATA_FAIL_CLOSED=false`

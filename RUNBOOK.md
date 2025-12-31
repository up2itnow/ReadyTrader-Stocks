## ReadyTrader-Stocks Runbook (Equity-Focused)

### Common operations

#### Verify health
- Use MCP tool: `get_health()`
- If health fails:
  - confirm required environment variables are set
  - confirm exchange endpoints are reachable (REST + websocket if enabled)
  - confirm rate limits and policy allowlists are not blocking requests

#### View metrics
- Use MCP tool: `get_metrics_snapshot()`
- Prometheus text format (no HTTP server): `get_metrics_prometheus()`

#### Kill switch (live trading)
- Set `TRADING_HALTED=true` and restart the container.

#### Rotate secrets
- Prefer keystore or remote signer in live environments.
- Rotate `CEX_*` credentials by updating env vars and restarting.

#### Debug execution failures
- Look for JSON logs with `event=tool_error` (and check `level`).
- In approve-each mode, use `list_pending_executions()` to inspect pending proposals.
- Re-run failed operations with an `idempotency_key` to avoid duplicates.

#### Websocket market streams
- Start public streams with `start_marketdata_ws(...)` and stop with `stop_marketdata_ws(...)`.
- For Binance private order updates, use `start_cex_private_ws(...)` / `stop_cex_private_ws(...)`, and inspect with
  `list_cex_private_updates(...)`.

---

### Incident playbooks (Phase 4)

#### 1) Rate limit storm (tools returning `rate_limited`)
- **Symptoms**:
  - Tools start failing with `rate_limited`
  - Metrics show rising `counters.rate_limited_total`
- **Triage**:
  - Call `get_metrics_snapshot()` and inspect:
    - `counters.rate_limit_checks_total`
    - `counters.rate_limited_total`
  - Check tool call patterns (agents may be looping/retrying too aggressively)
- **Mitigation**:
  - Reduce call frequency (prefer caching, batch calls, or use websocket streams)
  - Raise limits (carefully):
    - `RATE_LIMIT_DEFAULT_PER_MIN`
    - `RATE_LIMIT_EXECUTION_PER_MIN`
    - `RATE_LIMIT_<TOOL>_PER_MIN`

#### 2) Websocket disconnect loop (public streams)
- **Symptoms**:
  - `get_marketdata_status()` shows websocket stream `last_error`
  - Metrics show increasing websocket error/connect counters (e.g. `ws_*_error_total`)
- **Triage**:
  - Call `get_marketdata_status()` and inspect:
    - `ws_streams`
    - `stores.ws` freshness
  - Ensure outbound network access is available in the deployment environment
- **Mitigation**:
  - Stop and restart the stream:
    - `stop_marketdata_ws(exchange, market_type)`
    - `start_marketdata_ws(exchange, symbols_json, market_type)`
  - If unreliable, fall back to `ccxt_rest` and/or ingest your own feed.

#### 3) Exchange outage / degraded mode
- **Symptoms**:
  - CCXT calls failing (`ccxt_exchange_unavailable`, `ccxt_network_error`)
  - Private update pollers show errors / lag
- **Triage**:
  - Check `docs/EXCHANGES.md` (Supported vs Experimental expectations)
  - Use `get_cex_capabilities(exchange)` for `has.*` and market metadata
  - Check market data: `get_ticker(symbol)` meta → `candidates`
- **Mitigation**:
  - Switch market data sources (prefer websocket/ingest, reduce REST usage)
  - Temporarily disable live execution with `TRADING_HALTED=true`

#### 4) Signer unreachable (remote signer / keystore issues)
- **Symptoms**:
  - Live DEX execution fails with signing errors
  - Errors like `remote_signer_error` or signer initialization failures
- **Triage**:
  - Confirm signer configuration (`SIGNER_TYPE`, keystore path/password, remote signer URL)
  - Check logs for `tool_error` around execution tools
- **Mitigation**:
  - Halt live trading (`TRADING_HALTED=true`)
  - Fix signer connectivity/credentials, then restart

#### 5) Policy blocks (allowlists / limits)
- **Symptoms**:
  - Errors like `token_not_allowed`, `trade_amount_too_large`, `router_not_allowed`
- **Triage**:
  - Review `env.example` and current env values for `ALLOW_*`, `MAX_*`
  - If you are intentionally loosening limits, ensure Advanced Risk consent is accepted
- **Mitigation**:
  - Adjust allowlists/limits, or set a stricter risk profile
  - Keep `EXECUTION_APPROVAL_MODE=approve_each` while validating new configs

### Backup/restore (paper mode)
- Paper ledger is stored in `data/paper.db` (ignored by git).
- Back up by copying the file while the container is stopped.


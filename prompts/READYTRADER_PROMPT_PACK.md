## ReadyTrader-Stocks Prompt Pack

These are copy/paste prompts you can drop into Agent Zero, Claude, or any MCP-capable agent.

---

## Prompt 1 — 10-minute paper-mode evaluation

You have access to the ReadyTrader-Stocks MCP server. We are in PAPER_MODE=true.

Goals:
- Validate you can use the tools safely
- Produce a short “operator report” that proves the system works

Steps:
1) Call `get_health()` and summarize anything non-OK.
2) Call `deposit_paper_funds("USD", 10000)` for user `agent_zero`.
3) Place a paper limit order: `place_limit_order("buy", "AAPL", 10.0, 150.0)`.
4) Call `check_orders("AAPL")` until the order is filled (or explain why it won’t fill).
5) Call `get_address_balance` or report balances using paper tools.
6) Produce a final summary with:
   - final balances
   - portfolio value (if available)
   - any risk blocks encountered

Constraints:
- Do not attempt live trading.
- If you hit an error, call `get_health()` again and include the error code + message.

---

## Prompt 2 — Synthetic Stress Lab (deterministic)

We are in PAPER_MODE=true. I will provide strategy code. You will:
- run `run_synthetic_stress_test(strategy_code, config_json)`
- summarize tail risk and regime failures
- output recommended settings

Use this config as a baseline:
```json
{
  "master_seed": 1337,
  "scenarios": 200,
  "length": 500,
  "timeframe": "1h",
  "initial_capital": 10000,
  "start_price": 100,
  "base_vol": 0.015,
  "black_swan_prob": 0.03,
  "parabolic_prob": 0.03
}
```

Output requirements:
- Show max drawdown stats (p95 + max) and return tail (p05).
- List the worst-case seed(s) and their event metadata.
- Provide parameter recommendations (and explain what failure mode they address).

---

## Prompt 3 — Live trading preflight (DO NOT EXECUTE TRADES)

We are preparing for live mode, but you must not place any live orders.

Tasks:
1) Call `get_health()` and check:
   - trading halted state
   - policy allowlists/limits
   - brokerage configuration safety (API key presence)
2) Call `get_advanced_risk_disclosure()` but do not accept it.
3) Output a “go/no-go” checklist and what env vars the operator should set before enabling live trading.

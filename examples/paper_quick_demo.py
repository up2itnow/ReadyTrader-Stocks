"""
ReadyTrader-Crypto Phase 6 — Paper-mode quick demo (offline).

Goal: give a new user a 1-command way to validate that the paper trading engine works:
- deposits
- limit orders
- fills
- portfolio valuation + basic risk metrics

This script does NOT run the MCP server; it exercises the underlying engine directly so it
works without any MCP client configuration.
"""

import json
import tempfile
from pathlib import Path


def main() -> int:
    # Allow running from repo root without installing as a package.
    # (If executed from a different CWD, we add the repo root to sys.path.)
    import sys

    user_id = "demo_user"

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from core.paper import PaperTradingEngine

    with tempfile.TemporaryDirectory() as td:
        db_path = str(Path(td) / "paper_demo.db")
        engine = PaperTradingEngine(db_path=db_path)

        print("\n=== ReadyTrader-Crypto paper-mode quick demo ===")

        print("\n1) Deposit paper funds")
        print(engine.deposit(user_id, "USDC", 10_000.0))

        print("\n2) Place a limit BUY for ETH/USDT")
        print(engine.place_limit_order(user_id, "buy", "ETH/USDT", amount=1.0, price=2000.0))

        print("\n3) Simulate market moving down and fill open orders")
        fill_msgs = engine.check_open_orders("ETH/USDT", current_price=1950.0)
        print("\n".join(fill_msgs) if fill_msgs else "(no fills)")

        print("\n4) Check balances + portfolio value")
        balances = {
            "USDC": engine.get_balance(user_id, "USDC"),
            "ETH": engine.get_balance(user_id, "ETH"),
        }
        print(json.dumps(balances, indent=2))
        print(f"Portfolio value (USD): {engine.get_portfolio_value_usd(user_id):.2f}")

        print("\n5) Execute a market SELL (paper) and re-check portfolio value")
        print(engine.execute_trade(user_id, "sell", "ETH/USDT", amount=1.0, price=2200.0, rationale="Demo exit"))
        print(f"Portfolio value (USD): {engine.get_portfolio_value_usd(user_id):.2f}")

        try:
            metrics = engine.get_risk_metrics(user_id)
        except Exception:
            metrics = {}
        print("\n6) Risk metrics snapshot")
        print(json.dumps(metrics, indent=2))

    print("\nDone. Next: run `python examples/stress_test_demo.py` for the synthetic stress lab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


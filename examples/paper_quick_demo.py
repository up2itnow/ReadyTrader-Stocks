"""
ReadyTrader-Stocks — Paper-mode quick demo (offline).

Goal: give a new user a 1-command way to validate that the paper trading engine works:
- deposits
- limit orders
- fills
- portfolio valuation + basic risk metrics
"""

import json
import tempfile
from pathlib import Path


def main() -> int:
    import sys

    user_id = "demo_user"

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from core.paper import PaperTradingEngine

    with tempfile.TemporaryDirectory() as td:
        db_path = str(Path(td) / "paper_demo.db")
        engine = PaperTradingEngine(db_path=db_path)

        print("\n=== ReadyTrader-Stocks paper-mode quick demo ===")

        print("\n1) Deposit paper funds")
        print(engine.deposit(user_id, "USD", 10_000.0))

        print("\n2) Place a limit BUY for AAPL")
        print(engine.place_limit_order(user_id, "buy", "AAPL", amount=10.0, price=150.0))

        print("\n3) Simulate market moving down and fill open orders")
        fill_msgs = engine.check_open_orders("AAPL", current_price=149.0)
        print("\n".join(fill_msgs) if fill_msgs else "(no fills)")

        print("\n4) Check balances + portfolio value")
        balances = {
            "USD": engine.get_balance(user_id, "USD"),
            "AAPL": engine.get_balance(user_id, "AAPL"),
        }
        print(json.dumps(balances, indent=2))
        print(f"Portfolio value (USD): {engine.get_portfolio_value_usd(user_id):.2f}")

        print("\n5) Execute a market SELL (paper) and re-check portfolio value")
        print(engine.execute_trade(user_id, "sell", "AAPL", amount=10.0, price=160.0, rationale="Take profit demo"))
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

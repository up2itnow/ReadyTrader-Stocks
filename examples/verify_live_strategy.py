
import asyncio
import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from execution.stock_executor import StockExecutor

from strategy.moving_average import SmaStrategy


async def verify():
    print("--- Verifying Live Trading & Strategy ---")
    
    # 1. Test StockExecutor (Mock Mode)
    print("\n[Executor] Testing StockExecutor (Paper Mode)...")
    try:
        # We manually instantiate to test the class, independent of container which uses global settings
        executor = StockExecutor(mode="paper")
        bal = executor.fetch_balance()
        print(f"Mock Balance: {bal}")
        
        order = executor.place_order("AAPL", "buy", 10, 150.0)
        print(f"Mock Order: {order}")
        
        if order.get("status") == "filled":
            print("SUCCESS: StockExecutor (Paper) functional.")
        else:
            print("FAILURE: Mock order status incorrect.")
            
    except Exception as e:
        print(f"FAILED StockExecutor: {e}")

    # 2. Test Alpaca Initialization (Expect Failure without Keys)
    print("\n[Executor] Testing Alpaca Client Init (expecting error if keys missing)...")
    try:
        # We expect this to raise ValueError if keys are missing
        StockExecutor(mode="live")
        print("WARNING: Alpaca initialized? Keys might be set or check logic.")
    except ValueError as ve:
        print(f"SUCCESS: Correctly caught missing keys: {ve}")
    except Exception as e:
        print(f"FAILED: Unexpected error during Alpaca init: {e}")

    # 3. Test SMA Strategy
    print("\n[Strategy] Testing SMA Strategy on AAPL...")
    try:
        # SmaStrategy uses global_container.exchange_provider which we verified earlier
        strat = SmaStrategy("AAPL", short_window=5, long_window=10)
        res = strat.analyze()
        print(f"Strategy Result: {res}")
        
        if "signal" in res:
             print("SUCCESS: Strategy generated analysis.")
        else:
             print("FAILURE: Strategy output malformed.")
             
    except Exception as e:
        print(f"FAILED Strategy: {e}")

if __name__ == "__main__":
    asyncio.run(verify())


import asyncio
import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from app.core.container import global_container

async def verify():
    print("--- Verifying ReadyTrader-Stocks ---")
    
    # 1. Test Market Data (yfinance)
    try:
        ticker = global_container.marketdata_bus.fetch_ticker("AAPL")
        print(f"Ticker Object: {ticker}")
        # MarketDataResult(source='...', data={...}, meta={...})
        data = getattr(ticker, 'data', {})
        price = data.get('last')
        ts = data.get('timestamp_ms')
             
        print(f"Success: AAPL = {price} (Timestamp: {ts})")
        
        if price is None:
            raise ValueError("Could not extract price from ticker.data")
    except Exception as e:
        print(f"FAILED market data: {e}")
        return

    # 2. Test Paper Execution
    print("\n[Paper Execution] Placing a mock BUY order for AAPL...")
    try:
        # Deposit fake USD first
        user_id = "test_user"
        global_container.paper_engine.deposit(user_id, "USD", 10000.0)
        
        # Place Order (Limit)
        # Assuming current price is around ticker['last']
        # price variable already holds the last price from above
        buy_price = price * 0.99 # slightly below to sit on book, or match immediately?
        # Check logic: update_open_orders matches if price <= limit for buy?
        # Actually in paper_engine: if side == 'buy' and current_price <= price: fill.
        # So if we buy at 1.01 * price (limit higher than current), it should fill immediately.
        limit_price = price * 1.05 
        
        res = global_container.paper_engine.execute_trade(user_id, "buy", "AAPL", 10, limit_price, "Test Trade")
        print(f"Trade Result: {res}")
        
        # Check Balance
        bal = global_container.paper_engine.get_balance(user_id, "AAPL")
        print(f"Balance AAPL: {bal}")
        
        bal_usd = global_container.paper_engine.get_balance(user_id, "USD")
        print(f"Balance USD: {bal_usd}")
        
        if bal == 10:
            print("SUCCESS: Paper trade executed and balance updated.")
        else:
            print("FAILURE: Balance incorrect.")
            
    except Exception as e:
        print(f"FAILED paper execution: {e}")

if __name__ == "__main__":
    asyncio.run(verify())

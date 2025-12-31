from typing import Any, Dict

import pandas as pd
import ta
from RestrictedPython import compile_restricted, safe_globals, utility_builtins

from marketdata.exchange_provider import ExchangeProvider


class BacktestEngine:
    def __init__(self):
        self.exchange = ExchangeProvider()

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Fetch historical data and return as DataFrame."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            raise ValueError(f"Error fetching data: {str(e)}")

    def run(
        self,
        strategy_code: str,
        symbol: str,
        timeframe: str = "1h",
        initial_capital: float = 10000.0,
    ) -> Dict[str, Any]:
        """
        Run a backtest using provided strategy code.
        Strategy code must define a function: `def on_candle(candle, indicators, state): -> str ('buy', 'sell', 'hold')`
        """
        try:
            # 1. Fetch Data
            df = self.fetch_ohlcv(symbol, timeframe, limit=500)
            
            # 2. Add Indicators (Pre-calc for ease)
            df['rsi'] = ta.momentum.rsi(df['close'], window=14)
            df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
            df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
            
            # 3. Prepare Runtime Context
            
            # Define safe access policy
            def safe_getattr(obj, name):
                """Allow access to attributes that don't start with underscore."""
                if name.startswith('_'):
                    raise AttributeError(f"Access to private attribute '{name}' is forbidden")
                return getattr(obj, name)

            def safe_import(name, *args, **kwargs):
                """Restrict imports to a whitelist."""
                whitelist = ['math']
                if name in whitelist:
                    return __import__(name, *args, **kwargs)
                raise ImportError(f"Importing '{name}' is forbidden.")

            def safe_getitem(obj, key):
                if isinstance(key, str) and key.startswith("_"):
                    raise KeyError("Access to private keys is forbidden")
                return obj[key]

            def safe_setitem(obj, key, value):
                if isinstance(key, str) and key.startswith("_"):
                    raise KeyError("Access to private keys is forbidden")
                obj[key] = value
                return value

            # Construct safe global execution environment
            global_scope = safe_globals.copy()
            global_scope.update(utility_builtins)
            global_scope['__builtins__']['__import__'] = safe_import
            global_scope['_getattr_'] = safe_getattr
            global_scope["_getitem_"] = safe_getitem
            global_scope["_setitem_"] = safe_setitem
            global_scope["_getiter_"] = iter
            
            # Expose specific libraries safely (User must not use internal _methods)
            global_scope['pd'] = pd 
            global_scope['ta'] = ta
            
            # Execute the user's strategy definition securely
            try:
                byte_code = compile_restricted(strategy_code, '<inline>', 'exec')
                # RestrictedPython sandbox: exec is required to evaluate user strategy code safely.
                # Use the same dict for globals+locals so top-level vars are visible inside on_candle().
                exec(byte_code, global_scope, global_scope)  # nosec B102
            except Exception as e:
                return {"error": f"Strategy Compilation Error: {str(e)}"}
            
            if 'on_candle' not in global_scope:
                return {"error": "Strategy code must define 'def on_candle(close, rsi, state):' or similar"}

            on_candle = global_scope['on_candle']

            # 4. Simulation Loop
            capital = initial_capital
            position = 0.0 # Amount of asset
            trades = []
            state = {} # Persistent state for the strategy
            
            for i, row in df.iterrows():
                # Provide simple inputs for Phase 4 proof
                current_price = row['close']
                rsi = row['rsi']
                
                # Handling NaN for first few rows
                if pd.isna(rsi):
                    continue
                
                # Call Strategy
                try:
                    # Signature: on_candle(price, rsi, state) -> action
                    action = on_candle(current_price, rsi, state)
                except Exception as e:
                    return {"error": f"Runtime error in strategy at row {i}: {str(e)}"}
                
                # Execute Logic (Simple)
                if action == 'buy' and capital > 0:
                    # Buy All
                    amount = capital / current_price
                    position = amount
                    capital = 0
                    trades.append({'type': 'buy', 'price': current_price, 'time': str(row['timestamp'])})
                    
                elif action == 'sell' and position > 0:
                    # Sell All
                    capital = position * current_price
                    position = 0
                    trades.append({'type': 'sell', 'price': current_price, 'time': str(row['timestamp'])})
            
            # Final Value
            final_value = capital if capital > 0 else position * df.iloc[-1]['close']
            pnl = final_value - initial_capital
            pnl_percent = (pnl / initial_capital) * 100
            
            return {
                "symbol": symbol,
                "initial_capital": initial_capital,
                "final_value": round(final_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
                "total_trades": len(trades),
                "trades_log": trades[-5:] # Show last 5
            }
            
        except Exception as e:
            return {"error": f"Backtest Engine Error: {str(e)}"}

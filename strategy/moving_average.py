
import logging
import time
from typing import Any, Dict, List, Optional
import pandas as pd
import pandas_ta as ta

from marketdata.exchange_provider import ExchangeProvider
from app.core.container import global_container

logger = logging.getLogger(__name__)

class SmaStrategy:
    """
    Simple Moving Average (SMA) Crossover Strategy for Stocks.
    """
    def __init__(self, symbol: str, short_window: int = 20, long_window: int = 50):
        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window
        
    def analyze(self) -> Dict[str, Any]:
        """
        Fetch data, calculate indicators, and return signal.
        Signal: 1 (Buy), -1 (Sell), 0 (Hold)
        """
        # Fetch OHLCV using the container's exchange provider (yfinance)
        # We need enough data for the long window
        limit = self.long_window + 10 
        provider = global_container.exchange_provider
        
        try:
            ohlcv = provider.fetch_ohlcv(self.symbol, timeframe="1d", limit=limit)
            if not ohlcv or len(ohlcv) < self.long_window:
                logger.warning(f"Not enough data for {self.symbol}")
                return {"signal": 0, "reason": "insufficient_data"}
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df['close'] = df['close'].astype(float)
            
            # Calculate SMAs using pandas_ta
            df.ta.sma(length=self.short_window, append=True)
            df.ta.sma(length=self.long_window, append=True)
            
            # Get last two rows to check for crossover
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            short_col = f"SMA_{self.short_window}"
            long_col = f"SMA_{self.long_window}"
            
            # Check for Golden Cross (Short crosses above Long)
            if prev[short_col] <= prev[long_col] and curr[short_col] > curr[long_col]:
                return {
                    "signal": 1,
                    "reason": "golden_cross",
                    "short_val": curr[short_col],
                    "long_val": curr[long_col],
                    "price": curr['close']
                }
            
            # Check for Death Cross (Short crosses below Long)
            elif prev[short_col] >= prev[long_col] and curr[short_col] < curr[long_col]:
                return {
                    "signal": -1,
                    "reason": "death_cross",
                    "short_val": curr[short_col],
                    "long_val": curr[long_col],
                    "price": curr['close']
                }
                
            return {
                "signal": 0,
                "reason": "no_crossover",
                "short_val": curr[short_col],
                "long_val": curr[long_col],
                "price": curr['close']
            }
            
        except Exception as e:
            logger.error(f"Strategy error: {e}")
            return {"signal": 0, "error": str(e)}

if __name__ == "__main__":
    # Simple standardized test
    strat = SmaStrategy("AAPL", 5, 10) # shorter windows for testing likely availability
    print(f"Analyzing {strat.symbol}...")
    res = strat.analyze()
    print(f"Result: {res}")

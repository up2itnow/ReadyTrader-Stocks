from typing import Any, Dict

import pandas as pd
import ta


class RegimeDetector:
    def __init__(self):
        pass

    def detect(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze dataframe to determine market regime.
        Requires OHLCV data.
        Returns: {
            "regime": "TRENDING" | "RANGING" | "VOLATILE",
            "trend_strength": float (ADX),
            "volatility": float (ATR relative),
            "direction": "UP" | "DOWN" | "SIDEWAYS"
        }
        """
        # Ensure we have enough data
        if len(df) < 50:
            return {"error": "Not enough data for regime detection (need 50+ candles)"}

        # Calculate ADX (Average Directional Index) for Trend Strength
        # Window usually 14
        adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
        df['adx'] = adx.adx()
        df['di_plus'] = adx.adx_pos()
        df['di_neg'] = adx.adx_neg()
        
        # Calculate ATR (Average True Range) for Volatility
        atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14)
        df['atr'] = atr.average_true_range()
        
        # Get latest values
        current_adx = df['adx'].iloc[-1]
        current_atr = df['atr'].iloc[-1]
        current_close = df['close'].iloc[-1]
        current_di_plus = df['di_plus'].iloc[-1]
        current_di_neg = df['di_neg'].iloc[-1]

        # Logic
        regime = "RANGING"
        direction = "SIDEWAYS"
        
        # ADX Thresholds: < 20 Weak/Ranging, > 25 Trending, > 50 Strong
        if current_adx > 25:
            regime = "TRENDING"
            if current_di_plus > current_di_neg:
                direction = "UP"
            else:
                direction = "DOWN"
        
        # Volatility Check (ATR relative to price)
        # If ATR is > 2% of price, we consider it Volatile
        atr_pct = (current_atr / current_close) * 100
        if atr_pct > 2.0:
            regime = f"VOLATILE_{regime}" # e.g. VOLATILE_TRENDING
            
        return {
            "regime": regime,
            "direction": direction,
            "adx": round(current_adx, 2),
            "atr_pct": round(atr_pct, 2),
            "summary": f"Market is {regime} ({direction}). ADX: {current_adx:.1f}, Volatility: {atr_pct:.1f}%"
        }

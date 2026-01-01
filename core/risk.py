from typing import Any, Dict, Optional


class RiskGuardian:
    def __init__(self):
        pass

    def validate_trade(self, 
                      side: str, 
                      symbol: str, 
                      amount_usd: float, 
                      portfolio_value: float, 
                      sentiment_score: float = 0.0,
                      daily_loss_pct: float = 0.0,
                      current_drawdown_pct: float = 0.0,
                      force_approval: bool = False,
                      price: Optional[float] = None,
                      last_close_price: Optional[float] = None,
                      day_trades_count: int = 0) -> Dict[str, Any]:
        """
        Validate a trade against safety rules.
        """
        # Rule 0: System State Checks
        # Max Drawdown Check (10%)
        # If drawdown is 10%, we only allow reducing risk (SELLs), not BUYs?
        # Or we block everything? Usually block BUYs.
        if current_drawdown_pct >= 0.10 and side.lower() == 'buy':
             return {
                "allowed": False,
                "reason": f"Max Drawdown Limit Hit ({current_drawdown_pct:.1%}). Trading HALTED for Buys."
             }
             
        # Daily Loss Limit (5%)
        # If we lost 5% today, stop trading.
        # daily_loss_pct is usually negative (e.g. -0.05)
        if daily_loss_pct <= -0.05 and side.lower() == 'buy':
             return {
                "allowed": False,
                "reason": f"Daily Loss Limit Hit ({daily_loss_pct:.1%}). Trading HALTED for Buys."
             }

        # Rule 1: Position Sizing
        # Max 5% of portfolio per trade
        max_alloc_pct = 0.05
        if portfolio_value > 0:
            trade_pct = amount_usd / portfolio_value
            if trade_pct > max_alloc_pct:
                return {
                    "allowed": False,
                    "reason": f"Position size too large ({trade_pct:.1%}). Max allowed is {max_alloc_pct:.0%}."
                }

        # Rule 2: "Don't Catch Falling Knives"
        # If sentiment is very bearish (< -0.5) and trying to Buy
        if side.lower() == 'buy' and sentiment_score < -0.5:
             return {
                "allowed": False,
                "reason": "Guardian blocked BUY due to Extreme Bearish sentiment (Falling Knife protection)."
            }
            
        # Rule 3: Price Collar (Fat-finger protection - SEC Rule 15c3-5)
        if last_close_price and price:
            deviation = abs(price - last_close_price) / last_close_price
            if deviation > 0.05: # 5% collar
                return {
                    "allowed": False,
                    "reason": f"Price collar violation: {deviation:.2%} deviation from last close exceeds 5% limit."
                }

        # Rule 4: PDT (Pattern Day Trader) Check
        if day_trades_count >= 3 and portfolio_value < 25000:
             return {
                 "allowed": False,
                 "reason": "Pattern Day Trader protection: >3 day trades in account under $25k."
             }
            
        # Rule 5: Large Trade Confirmation
        # Any trade > $5000 requires manual approval even if allowed by logic
        needs_confirmation = False
        if amount_usd > 5000.0:
            needs_confirmation = True

        return {
            "allowed": True,
            "needs_confirmation": needs_confirmation,
            "reason": "Trade looks safe but requires manual confirmation." if needs_confirmation else "Trade looks safe."
        }

import sqlite3

import pandas as pd


class Learner:
    """
    Analyzes past trades to generate insights for the Agent.
    """
    def __init__(self, db_path: str = "paper.db"):
        self.db_path = db_path

    def analyze_performance(self, cur_symbol: str = None) -> str:
        """
        Review past trades and generate a summary of lessons.
        """
        conn = sqlite3.connect(self.db_path)
        
        # Fetch filled orders with rationale
        query = (
            "SELECT symbol, side, amount, price, total_value, rationale, pnl_realized "
            "FROM orders WHERE status='filled'"
        )
        if cur_symbol:
            query += f" AND symbol='{cur_symbol}'"
            
        try:
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                return "No past trades to learn from yet."

            # Calculate basic stats
            # Note: pnl_realized needs to be populated when closing positions.
            # For now, we might not have it fully wired in paper_engine, so we rely on rationale review.
            
            # Simple Heuristic: Look for patterns in rationale of losing trades vs winning trades
            # For this MVP, we just summarize the last 5 trades to give context to the LLM.
            
            recent_trades = df.tail(5)
            summary = "Recent Trade History & Rationale:\n"
            
            for index, row in recent_trades.iterrows():
                pnl = row.get('pnl_realized') # Might be None
                outcome = "Unknown"
                if pnl:
                     outcome = "PROFIT" if pnl > 0 else "LOSS"
                
                summary += (
                    f"- {row['side']} {row['symbol']} @ {row['price']}: {outcome}. "
                    f"Rationale: \"{row['rationale']}\"\n"
                )
                
            return summary
            
        except Exception as e:
            return f"Error analyzing performance: {str(e)}"
            
    def save_lesson(self, lesson: str):
        # Could save high-level takeaways to a separate table
        pass

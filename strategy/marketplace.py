import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class StrategyArtifact:
    strategy_id: str
    name: str
    author: str
    backtest_pnl_pct: float
    backtest_sharpe: float
    logic_summary: str
    config_json: str
    created_at: int

class StrategyRegistry:
    """
    Local marketplace for saving and sharing agent strategies.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("REALTRADER_STRATEGY_DB_PATH", os.getenv("STRATEGY_DB_PATH", "data/strategies.db"))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    strategy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    author TEXT NOT NULL,
                    backtest_pnl_pct REAL,
                    backtest_sharpe REAL,
                    logic_summary TEXT,
                    config_json TEXT,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_name ON strategies(name)")

    def register_strategy(self, name: str, author: str, pnl: float, sharpe: float, summary: str, config: Dict[str, Any]) -> StrategyArtifact:
        strategy_id = secrets.token_hex(6)
        artifact = StrategyArtifact(
            strategy_id=strategy_id,
            name=name,
            author=author,
            backtest_pnl_pct=float(pnl),
            backtest_sharpe=float(sharpe),
            logic_summary=summary,
            config_json=json.dumps(config),
            created_at=int(time.time())
        )
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO strategies (strategy_id, name, author, backtest_pnl_pct, backtest_sharpe, logic_summary, config_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                artifact.strategy_id,
                artifact.name,
                artifact.author,
                artifact.backtest_pnl_pct,
                artifact.backtest_sharpe,
                artifact.logic_summary,
                artifact.config_json,
                artifact.created_at
            ))
        return artifact

    def list_strategies(self, limit: int = 10) -> List[StrategyArtifact]:
        query = "SELECT * FROM strategies ORDER BY backtest_pnl_pct DESC LIMIT ?"
        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, (limit,))
            for row in cursor:
                results.append(StrategyArtifact(*row))
        return results

    def get_strategy(self, strategy_id: str) -> Optional[StrategyArtifact]:
        query = "SELECT * FROM strategies WHERE strategy_id = ?"
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(query, (strategy_id,)).fetchone()
            if row:
                return StrategyArtifact(*row)
        return None

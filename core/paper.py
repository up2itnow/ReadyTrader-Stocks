import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional


class PaperTradingEngine:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("READYTRADER_PAPER_DB_PATH", os.getenv("PAPER_DB_PATH", "data/paper.db"))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Create balances table
        c.execute('''CREATE TABLE IF NOT EXISTS balances
                     (user_id TEXT, asset TEXT, amount REAL, 
                      PRIMARY KEY (user_id, asset))''')
        # Create orders table
        # NOTE: Prior versions had a schema bug (duplicate column names). We create a correct schema here.
        c.execute(
            '''CREATE TABLE IF NOT EXISTS orders
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id TEXT NOT NULL,
                      timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                      side TEXT NOT NULL,
                      symbol TEXT NOT NULL,
                      amount REAL NOT NULL,
                      price REAL NOT NULL,
                      total_value REAL NOT NULL,
                      type TEXT DEFAULT 'market',
                      status TEXT DEFAULT 'filled',
                      rationale TEXT,
                      pnl_realized REAL)'''
        )

        # Equity snapshots for real drawdown/daily PnL metrics
        c.execute(
            '''CREATE TABLE IF NOT EXISTS equity_snapshots
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id TEXT NOT NULL,
                      timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                      equity_usd REAL NOT NULL)'''
        )

        # Asset price cache (derived from executed trades; no external price feed required)
        c.execute(
            '''CREATE TABLE IF NOT EXISTS asset_prices
                     (asset TEXT PRIMARY KEY,
                      price_usd REAL NOT NULL,
                      updated_at TEXT DEFAULT CURRENT_TIMESTAMP)'''
        )
        conn.commit()
        
        # Schema Migration: ensure required columns exist for older DBs
        cols = {row[1] for row in c.execute("PRAGMA table_info(orders)").fetchall()}
        if "rationale" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN rationale TEXT")
        if "pnl_realized" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN pnl_realized REAL")
        if "type" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN type TEXT DEFAULT 'market'")
        if "status" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'filled'")
        conn.commit()
            
        conn.close()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _set_asset_price_usd(self, asset: str, price_usd: float) -> None:
        if price_usd <= 0:
            return
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO asset_prices (asset, price_usd, updated_at) VALUES (?, ?, ?)",
            (asset.upper(), float(price_usd), self._now_iso()),
        )
        conn.commit()
        conn.close()

    def _get_asset_price_usd(self, asset: str) -> Optional[float]:
        a = asset.upper()
        if a in {"USD", "USDT", "USDC", "DAI"}:
            return 1.0
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT price_usd FROM asset_prices WHERE asset=?", (a,))
        row = c.fetchone()
        conn.close()
        return float(row[0]) if row else None

    def get_portfolio_value_usd(self, user_id: str) -> float:
        """
        Mark-to-market portfolio using last known executed prices (derived from paper trades).
        Stablecoins are valued at $1.
        Assets without a known price are excluded (conservative).
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT asset, amount FROM balances WHERE user_id=?", (user_id,))
        rows = c.fetchall()
        conn.close()

        total = 0.0
        for asset, amount in rows:
            if amount is None:
                continue
            px = self._get_asset_price_usd(asset)
            if px is None:
                continue
            total += float(amount) * float(px)
        return float(total)

    def _snapshot_equity(self, user_id: str) -> None:
        equity = self.get_portfolio_value_usd(user_id)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO equity_snapshots (user_id, timestamp, equity_usd) VALUES (?, ?, ?)",
            (user_id, self._now_iso(), float(equity)),
        )
        conn.commit()
        conn.close()
        
    def get_balance(self, user_id: str, asset: str) -> float:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT amount FROM balances WHERE user_id=? AND asset=?", (user_id, asset))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0.0
        
    def deposit(self, user_id: str, asset: str, amount: float) -> str:
        current = self.get_balance(user_id, asset)
        new_balance = current + amount
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO balances (user_id, asset, amount) VALUES (?, ?, ?)",
                  (user_id, asset, new_balance))
        conn.commit()
        conn.close()
        self._snapshot_equity(user_id)
        return f"Deposited {amount} {asset}. New Balance: {new_balance}"

    def reset_wallet(self, user_id: str) -> str:
        """Clear all balances and trade history for a user in paper mode."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM balances WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM orders WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM equity_snapshots WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return f"Paper wallet and history for {user_id} have been reset."

    def _parse_symbol(self, symbol: str) -> tuple[str, str]:
        """
        Parse symbol into (base, quote).
        If no slash, assume it's a Stock ticker quoted in USD.
        e.g. "AAPL" -> ("AAPL", "USD")
        e.g. "BTC/USDT" -> ("BTC", "USDT")
        """
        s = symbol.strip().upper()
        if '/' in s:
            parts = s.split('/', 1)
            return parts[0], parts[1]
        # For stocks, base is the ticker, quote is USD
        return s, "USD"

    def place_limit_order(self, user_id: str, side: str, symbol: str, amount: float, price: float) -> str:
        """
        Place a limit order. Reserve funds immediately.
        """
        base, quote = self._parse_symbol(symbol)
        total_value = amount * price
        
        # Check simulated balance and reserve
        if side == 'buy':
            balance = self.get_balance(user_id, quote)
            if balance < total_value:
                return f"Insufficient fund. Have {balance} {quote}, need {total_value}"
            # Lock funds (deduct now)
            self.deposit(user_id, quote, -total_value)
            
        elif side == 'sell':
            balance = self.get_balance(user_id, base)
            if balance < amount:
                return f"Insufficient fund. Have {balance} {base}, need {amount}"
            # Lock funds
            self.deposit(user_id, base, -amount)
            
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO orders (user_id, side, symbol, amount, price, total_value, type, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'limit', 'open')",
            (user_id, side, symbol, amount, price, total_value),
        )
        order_id = c.lastrowid
        conn.commit()
        conn.close()
        return f"Order Placed: {side.upper()} {amount} {symbol} @ {price}. ID: {order_id}"

    def check_open_orders(self, symbol: str, current_price: float) -> List[str]:
        """
        Check and fill open orders based on current price.
        Returns a list of messages for filled orders.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Find open orders for this symbol
        c.execute(
            "SELECT id, user_id, side, amount, price, total_value "
            "FROM orders WHERE symbol=? AND status='open'",
            (symbol,),
        )
        orders = c.fetchall()
        
        filled_msgs = []
        base, quote = self._parse_symbol(symbol)
        
        for order in orders:
            oid, uid, side, amt, price, val = order
            
            fill = False
            if side == 'buy' and current_price <= price:
                fill = True
                # Give user the Base asset (Quote was deducted at placement)
                self.deposit(uid, base, amt)
                
            elif side == 'sell' and current_price >= price:
                fill = True
                # Give user the Quote asset (Base was deducted at placement)
                self.deposit(uid, quote, val) # val was amt * limit_price
                
            if fill:
                c.execute("UPDATE orders SET status='filled' WHERE id=?", (oid,))
                filled_msgs.append(f"Order #{oid} FILLED: {side.upper()} {amt} {symbol} @ {price}")
                # Update derived price cache from the fill price (best available for metrics)
                self._set_asset_price_usd(quote, 1.0 if quote.upper() in {"USDT", "USDC", "DAI", "USD"} else 1.0)
                if quote.upper() in {"USDT", "USDC", "DAI", "USD"}:
                    self._set_asset_price_usd(base, float(price))
                self._snapshot_equity(uid)
                
        conn.commit()
        conn.close()
        return filled_msgs
        
    def execute_trade(
        self,
        user_id: str,
        side: str,
        symbol: str,
        amount: float,
        price: float,
        rationale: str = "",
    ) -> str:
        """
        Execute a paper trade.
        """
        base, quote = self._parse_symbol(symbol)
        
        # If price is 0, try to fetch it from cache or mock
        if price <= 0:
            cached_price = self._get_asset_price_usd(base)
            if cached_price is None:
                raise ValueError(f"Price for {base} is unknown and pulse price was not provided. Execution failed (Zero-Mock Policy).")
            price = cached_price
        
            
        total_value = amount * price
        
        # Check simulated balance
        if side == 'buy':
            # Need quote asset (USDT)
            balance = self.get_balance(user_id, quote)
            if balance < total_value:
                return f"Insufficient fund. Have {balance} {quote}, need {total_value}"
            
            # Update balances
            self.deposit(user_id, quote, -total_value)
            self.deposit(user_id, base, amount)
            
        elif side == 'sell':
            # Need base asset (BTC)
            balance = self.get_balance(user_id, base)
            if balance < amount:
                return f"Insufficient fund. Have {balance} {base}, need {amount}"
            
            # Update balances
            self.deposit(user_id, base, -amount)
            self.deposit(user_id, quote, total_value)
            
        # Log order
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO orders (user_id, side, symbol, amount, price, total_value, rationale) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, side, symbol, amount, price, total_value, rationale),
        )
        conn.commit()
        conn.close()

        # Update derived price cache (if quote looks like USD stable)
        if quote.upper() in {"USDT", "USDC", "DAI", "USD"}:
            self._set_asset_price_usd(base, float(price))
            self._set_asset_price_usd(quote, 1.0)
        self._snapshot_equity(user_id)
        
        return (
            f"Paper Trade Executed: {side.upper()} {amount} {symbol} @ {price}. "
            f"Value: {total_value} {quote}. Rationale: {rationale}"
        )

    def get_risk_metrics(self, user_id: str) -> Dict[str, float]:
        """
        Calculate risk metrics for the user.
        Returns: { 'daily_pnl_pct': float, 'drawdown_pct': float }
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT timestamp, equity_usd FROM equity_snapshots WHERE user_id=? ORDER BY timestamp ASC",
            (user_id,),
        )
        rows = c.fetchall()
        conn.close()

        if not rows:
            return {"daily_pnl_pct": 0.0, "drawdown_pct": 0.0}

        # Compute drawdown (fraction, e.g. 0.10 for 10%)
        peak = float(rows[0][1])
        trough_drawdown = 0.0
        for _, eq in rows:
            eqv = float(eq)
            if eqv > peak:
                peak = eqv
            if peak > 0:
                dd = (peak - eqv) / peak
                if dd > trough_drawdown:
                    trough_drawdown = dd

        # Daily PnL%: compare last snapshot vs first snapshot of current UTC day
        today = self._now_iso()[:10]  # YYYY-MM-DD
        start_equity = float(rows[0][1])
        for ts, eq in rows:
            if str(ts).startswith(today):
                start_equity = float(eq)
                break
        end_equity = float(rows[-1][1])
        daily_pct = 0.0
        if start_equity > 0:
            daily_pct = (end_equity - start_equity) / start_equity

        return {"daily_pnl_pct": float(daily_pct), "drawdown_pct": float(trough_drawdown)}

"""
Database initialization script.

Creates SQLite database with schema for:
- OHLCV candle data
- Trade decisions
- System state
- Performance metrics
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path


def create_database(db_path: str = "data/trading.db") -> None:
    """
    Create SQLite database with all required tables.
    
    Args:
        db_path: Path to database file
    """
    # Ensure data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Connect to database (creates if doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Creating database at: {db_path}")
    
    # =========================================================================
    # OHLCV CANDLE DATA
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(symbol, timeframe, timestamp)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe 
        ON candles(symbol, timeframe, timestamp DESC)
    """)
    
    # =========================================================================
    # REGIME CLASSIFICATIONS
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            regime TEXT NOT NULL,
            confidence REAL NOT NULL,
            tradable INTEGER NOT NULL,
            atr REAL,
            efficiency_ratio REAL,
            volume_ratio REAL,
            created_at TEXT NOT NULL,
            UNIQUE(symbol, timestamp)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_regimes_symbol_timestamp
        ON regimes(symbol, timestamp DESC)
    """)
    
    # =========================================================================
    # TRADE DECISIONS
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            decision TEXT NOT NULL,
            regime TEXT NOT NULL,
            strategy TEXT,
            price REAL NOT NULL,
            size REAL,
            side TEXT,
            reason TEXT,
            risk_percent REAL,
            created_at TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_decisions_timestamp
        ON decisions(timestamp DESC)
    """)
    
    # =========================================================================
    # EXECUTED TRADES
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            entry_time INTEGER NOT NULL,
            size REAL NOT NULL,
            exit_price REAL,
            exit_time INTEGER,
            pnl REAL,
            pnl_percent REAL,
            fees REAL,
            status TEXT NOT NULL,
            strategy TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # =========================================================================
    # SYSTEM STATE
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            capital REAL NOT NULL,
            peak_capital REAL NOT NULL,
            drawdown_percent REAL NOT NULL,
            daily_pnl REAL NOT NULL,
            trades_today INTEGER NOT NULL,
            consecutive_losses INTEGER NOT NULL,
            is_kill_switch_active INTEGER NOT NULL,
            last_trade_time INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    
    # =========================================================================
    # PERFORMANCE METRICS (for weekly reviews)
    # =========================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_start INTEGER NOT NULL,
            period_end INTEGER NOT NULL,
            total_trades INTEGER NOT NULL,
            winning_trades INTEGER NOT NULL,
            losing_trades INTEGER NOT NULL,
            total_pnl REAL NOT NULL,
            win_rate REAL NOT NULL,
            avg_win REAL NOT NULL,
            avg_loss REAL NOT NULL,
            expectancy REAL NOT NULL,
            max_drawdown REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    
    # Print table counts
    tables = ['candles', 'regimes', 'decisions', 'trades', 'system_state', 'performance_metrics']
    print("\n✅ Database created successfully")
    print("\nTables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} rows")
    
    conn.close()


if __name__ == "__main__":
    db_path = os.getenv('DB_PATH', 'data/trading.db')
    create_database(db_path)
    print(f"\n📁 Database location: {os.path.abspath(db_path)}")
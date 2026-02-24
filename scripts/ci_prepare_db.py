"""Prepare a minimal SQLite `trading.db` with a `candles` table for CI.

This creates the DB at `DB_PATH` from `SYSTEM_CONFIG` (or env var) and
populates it with deterministic synthetic OHLCV data sufficient for tests.
"""
import sqlite3
import time
from datetime import datetime, timedelta, timezone
import os
from config.system_config import SYSTEM_CONFIG


def prepare_db(path: str, rows: int = 1000):
    if os.path.exists(path):
        print(f"CI DB already exists at {path}; removing and recreating")
        try:
            os.remove(path)
        except Exception:
            pass

    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE candles (
        symbol TEXT,
        timeframe TEXT,
        timestamp INTEGER PRIMARY KEY,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        created_at TEXT
    )
    """)

    # Generate `rows` hourly candles ending now
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=rows)

    symbol = SYSTEM_CONFIG.TRADING_PAIR
    timeframe = SYSTEM_CONFIG.PRIMARY_TIMEFRAME

    ts = int(start.timestamp() * 1000)
    price = 20000.0

    for i in range(rows):
        open_p = price + (i % 10) * 0.1
        close_p = open_p + ((-1) ** i) * 1.0
        high_p = max(open_p, close_p) + 0.5
        low_p = min(open_p, close_p) - 0.5
        volume = 1.0 + (i % 5) * 0.1

        cur.execute(
            "INSERT INTO candles (symbol, timeframe, timestamp, open, high, low, close, volume, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (symbol, timeframe, ts, open_p, high_p, low_p, close_p, volume, datetime.now(timezone.utc).isoformat()),
        )

        ts += 3600 * 1000  # advance 1 hour in ms

    conn.commit()
    conn.close()
    print(f"Created CI DB at {path} with {rows} candles for {symbol} {timeframe}")


if __name__ == '__main__':
    db_path = os.getenv('DB_PATH', SYSTEM_CONFIG.DB_PATH)
    prepare_db(db_path, rows=int(os.getenv('CI_CANDLES', '1000')))

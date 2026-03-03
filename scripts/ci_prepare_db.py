"""Prepare a minimal SQLite `trading.db` with a `candles` table for CI.

This creates the DB at `DB_PATH` from `SYSTEM_CONFIG` (or env var) and
populates it with deterministic synthetic OHLCV data sufficient for tests.
"""
import sqlite3
import time
from datetime import datetime, timedelta, timezone
import os
import random
import math
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
    # Use a deterministic random seed for CI reproducibility
    rnd = random.Random(42)
    price = 20000.0

    for i in range(rows):
        # Simulate a gentle random walk in price
        drift = rnd.gauss(0, 0.001)
        price = max(1.0, price * (1.0 + drift))

        # Add intrabar variation
        open_p = price + rnd.uniform(-0.5, 0.5)
        close_p = price + rnd.uniform(-1.0, 1.0)
        high_p = max(open_p, close_p) + abs(rnd.gauss(0, 0.5))
        low_p = min(open_p, close_p) - abs(rnd.gauss(0, 0.5))

        # Volume with occasional spikes
        base_vol = 50.0 + rnd.gauss(0, 10.0)
        if rnd.random() < 0.03:
            volume = base_vol * (3.0 + rnd.random() * 5.0)
        else:
            volume = max(0.1, base_vol)

        cur.execute(
            "INSERT INTO candles (symbol, timeframe, timestamp, open, high, low, close, volume, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (symbol, timeframe, ts, float(open_p), float(high_p), float(low_p), float(close_p), float(volume), datetime.now(timezone.utc).isoformat()),
        )

        ts += 3600 * 1000  # advance 1 hour in ms

    conn.commit()
    conn.close()
    print(f"Created CI DB at {path} with {rows} candles for {symbol} {timeframe}")


if __name__ == '__main__':
    db_path = os.getenv('DB_PATH', SYSTEM_CONFIG.DB_PATH)
    prepare_db(db_path, rows=int(os.getenv('CI_CANDLES', '1000')))

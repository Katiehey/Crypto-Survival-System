"""
Tests for data fetcher module.
"""

import pytest
import sqlite3
import os
from datetime import datetime
from data.fetcher import DataFetcher
from config.system_config import SYSTEM_CONFIG


@pytest.fixture
def test_db():
    """Create temporary test database."""
    test_db_path = "data/test_trading.db"
    
    # Create test database
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    
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
    
    conn.commit()
    conn.close()
    
    yield test_db_path
    
    # Cleanup
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_fetcher_initialization(test_db):
    """Test data fetcher can be initialized."""
    fetcher = DataFetcher(db_path=test_db)
    assert fetcher is not None
    assert fetcher.db_path == test_db


def test_store_ohlcv(test_db):
    """Test storing OHLCV data."""
    fetcher = DataFetcher(db_path=test_db)
    
    # Sample OHLCV data
    ohlcv = [
        [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 100.5],
        [1704070800000, 42300.0, 42800.0, 42100.0, 42600.0, 120.3],
    ]
    
    count = fetcher.store_ohlcv("BTC/USDT", "1h", ohlcv)
    
    assert count == 2
    assert fetcher.get_candle_count("BTC/USDT", "1h") == 2


def test_store_duplicate_candles(test_db):
    """Test that duplicate candles are handled correctly."""
    fetcher = DataFetcher(db_path=test_db)
    
    ohlcv = [
        [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 100.5],
    ]
    
    # Store once
    count1 = fetcher.store_ohlcv("BTC/USDT", "1h", ohlcv)
    
    # Store again (duplicate)
    count2 = fetcher.store_ohlcv("BTC/USDT", "1h", ohlcv)
    
    # Should still have only 1 candle
    assert fetcher.get_candle_count("BTC/USDT", "1h") == 1


def test_get_latest_timestamp(test_db):
    """Test getting latest timestamp."""
    fetcher = DataFetcher(db_path=test_db)
    
    # No data initially
    latest = fetcher.get_latest_timestamp("BTC/USDT", "1h")
    assert latest is None
    
    # Add data
    ohlcv = [
        [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 100.5],
        [1704070800000, 42300.0, 42800.0, 42100.0, 42600.0, 120.3],
    ]
    fetcher.store_ohlcv("BTC/USDT", "1h", ohlcv)
    
    # Get latest
    latest = fetcher.get_latest_timestamp("BTC/USDT", "1h")
    assert latest == 1704070800000


def test_load_candles(test_db):
    """Test loading candles as DataFrame."""
    fetcher = DataFetcher(db_path=test_db)
    
    # Add data
    ohlcv = [
        [1704067200000, 42000.0, 42500.0, 41800.0, 42300.0, 100.5],
        [1704070800000, 42300.0, 42800.0, 42100.0, 42600.0, 120.3],
    ]
    fetcher.store_ohlcv("BTC/USDT", "1h", ohlcv)
    
    # Load as DataFrame
    df = fetcher.load_candles("BTC/USDT", "1h")
    
    assert len(df) == 2
    assert 'open' in df.columns
    assert 'high' in df.columns
    assert 'low' in df.columns
    assert 'close' in df.columns
    assert 'volume' in df.columns
    assert 'datetime' in df.columns


def test_load_candles_with_limit(test_db):
    """Test loading candles with limit."""
    fetcher = DataFetcher(db_path=test_db)
    
    # Add multiple candles
    ohlcv = [
        [1704067200000 + i*3600000, 42000.0, 42500.0, 41800.0, 42300.0, 100.5]
        for i in range(10)
    ]
    fetcher.store_ohlcv("BTC/USDT", "1h", ohlcv)
    
    # Load with limit
    df = fetcher.load_candles("BTC/USDT", "1h", limit=5)
    
    assert len(df) == 5


def test_store_empty_ohlcv(test_db):
    """Test storing empty OHLCV list."""
    fetcher = DataFetcher(db_path=test_db)
    
    count = fetcher.store_ohlcv("BTC/USDT", "1h", [])
    
    assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
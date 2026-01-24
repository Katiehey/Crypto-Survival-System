"""
Tests for backtest data loader.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import sqlite3
import os

from backtest.data_loader import BacktestDataLoader


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database with sample data."""
    db_path = tmp_path / "test_backtest.db"
    
    # Create database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE candles (
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
    
    # Insert sample data (100 candles)
    n = 100
    base_time = int(datetime(2024, 1, 1).replace(tzinfo=timezone.utc).timestamp() * 1000)
    
    for i in range(n):
        timestamp = base_time + (i * 3600000)  # 1 hour intervals
        price = 42000 + (i * 10) + np.random.randn() * 100
        
        cursor.execute("""
            INSERT INTO candles
            (symbol, timeframe, timestamp, open, high, low, close, volume, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'BTC/USDT', '1h', timestamp,
            price, price + 50, price - 50, price + 10,
            100 + np.abs(np.random.randn() * 10),
            datetime.now().isoformat()
        ))
    
    conn.commit()
    conn.close()
    
    yield str(db_path)
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


class TestBacktestDataLoader:
    """Test data loader functionality."""
    
    def test_initialization(self, test_db):
        """Test loader can be initialized."""
        loader = BacktestDataLoader(db_path=test_db)
        
        assert loader.symbol == 'BTC/USDT'
        assert loader.timeframe == '1h'
    
    def test_load_data(self, test_db):
        """Test loading data from database."""
        loader = BacktestDataLoader(db_path=test_db)
        
        df = loader.load_data(limit=50)
        
        assert len(df) == 50
        assert 'close' in df.columns
        assert 'volume' in df.columns
    
    def test_load_data_with_dates(self, test_db):
        """Test loading data with date range."""
        loader = BacktestDataLoader(db_path=test_db)
        
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        
        df = loader.load_data(start_date=start, end_date=end)
        
        # Should have roughly 24 candles (1 day of hourly data)
        assert 20 <= len(df) <= 30
    
    def test_validate_data_success(self, test_db):
        """Test data validation with valid data."""
        loader = BacktestDataLoader(db_path=test_db)
        
        df = loader.load_data(limit=50)
        
        # Should not raise
        loader._validate_data(df)
    
    def test_validate_data_missing_columns(self):
        """Test validation catches missing columns."""
        loader = BacktestDataLoader()
        
        df = pd.DataFrame({
            'close': [42000, 42100]
            # Missing other required columns
        })
        
        with pytest.raises(ValueError, match="Missing required columns"):
            loader._validate_data(df)
    
    def test_validate_data_negative_prices(self):
        """Test validation catches negative prices."""
        loader = BacktestDataLoader()
        
        df = pd.DataFrame({
            'timestamp': [1, 2],
            'open': [42000, 42100],
            'high': [42500, 42600],
            'low': [41500, -100],  # Negative!
            'close': [42000, 42100],
            'volume': [100, 110]
        })
        
        with pytest.raises(ValueError, match="non-positive prices"):
            loader._validate_data(df)
    
    def test_validate_data_not_chronological(self):
        """Test validation catches non-chronological data."""
        loader = BacktestDataLoader()
        
        df = pd.DataFrame({
            'timestamp': [2, 1],  # Wrong order!
            'open': [42000, 42100],
            'high': [42500, 42600],
            'low': [41500, 41600],
            'close': [42000, 42100],
            'volume': [100, 110]
        })
        
        with pytest.raises(ValueError, match="not in chronological order"):
            loader._validate_data(df)
    
    def test_prepare_data(self, test_db):
        """Test data preparation (features + regimes)."""
        loader = BacktestDataLoader(db_path=test_db)
        
        df_raw = loader.load_data(limit=100)
        df_prepared = loader.prepare_data(df_raw)
        
        # Check features added
        assert 'atr' in df_prepared.columns
        assert 'efficiency_ratio' in df_prepared.columns
        assert 'volume_ratio' in df_prepared.columns
        
        # Check regimes added
        assert 'regime' in df_prepared.columns
        assert 'regime_confidence' in df_prepared.columns
    
    def test_load_and_prepare(self, test_db):
        """Test complete load and prepare workflow."""
        loader = BacktestDataLoader(db_path=test_db)
        
        df = loader.load_and_prepare(limit=100)
        
        # Should have all features and regimes
        assert 'regime' in df.columns
        assert 'atr' in df.columns
        assert len(df) == 100
    
    def test_get_data_summary(self, test_db):
        """Test data summary generation."""
        loader = BacktestDataLoader(db_path=test_db)
        
        df = loader.load_and_prepare(limit=50)
        summary = loader.get_data_summary(df)
        
        assert 'total_candles' in summary
        assert summary['total_candles'] == 50
        assert 'price_range' in summary
        assert 'regime_distribution' in summary
    
    def test_no_data_available(self, tmp_path):
        """Test handling of empty database."""
        # Create empty database
        empty_db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(empty_db))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE candles (
                id INTEGER PRIMARY KEY,
                symbol TEXT, timeframe TEXT, timestamp INTEGER,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        loader = BacktestDataLoader(db_path=str(empty_db))
        
        with pytest.raises(ValueError, match="No data available"):
            loader.load_data()


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
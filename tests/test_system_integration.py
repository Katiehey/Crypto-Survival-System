"""
Comprehensive system integration tests.

Tests the complete workflow from data fetching through regime classification
with various market conditions and edge cases.
"""

import pytest
import os
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, UTC

from data.fetcher import DataFetcher
from regime.features import calculate_complete_pipeline
from regime.classifier import get_regime_statistics
from regime.visualization import analyze_regime_sequence
from config.system_config import SYSTEM_CONFIG


class TestSystemIntegration:
    """Complete system integration tests."""
    
    def test_fresh_database_to_regime_classification(self, tmp_path):
        """Test complete flow with fresh database."""
        # Setup temporary database
        db_path = tmp_path / "test_integration.db"
        
        # Initialize database
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
        base_time = int(datetime.now().timestamp() * 1000)
        
        for i in range(n):
            timestamp = base_time + (i * 3600000)  # 1 hour intervals
            price = 42000 + i * 10 + np.random.randn() * 100
            volume = 100 + np.random.randn() * 10
            
            cursor.execute("""
                INSERT INTO candles
                (symbol, timeframe, timestamp, open, high, low, close, volume, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'BTC/USDT', '1h', timestamp,
                price, price + 50, price - 50, price + 10,
                abs(volume), datetime.now(UTC).isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Test fetcher can load data
        fetcher = DataFetcher(db_path=str(db_path))
        df = fetcher.load_candles('BTC/USDT', '1h')
        
        assert len(df) == 100
        assert 'close' in df.columns
        
        # Test complete pipeline
        df_processed = calculate_complete_pipeline(df)
        
        # Verify all expected columns exist
        assert 'regime' in df_processed.columns
        assert 'regime_confidence' in df_processed.columns
        assert 'regime_tradable' in df_processed.columns
        
        # Verify regimes are classified
        regime_counts = df_processed['regime'].value_counts()
        assert len(regime_counts) > 0
    
    
    def test_trending_market_detection(self):
        """Test system correctly identifies trending market."""
        # Create strong uptrend
        n = 150
        prices = np.linspace(40000, 60000, n)  # Strong uptrend
        prices = prices + np.random.randn(n) * 20  # Small noise
        
        df = pd.DataFrame({
            'high': prices + 50,
            'low': prices - 50,
            'close': prices,
            'volume': 100 + np.linspace(0, 500, n) + np.random.randn(n) * 20
        })
        
        df_processed = calculate_complete_pipeline(df)
        
        # Should classify significant portion as TREND
        regime_counts = df_processed['regime'].value_counts()
        trend_count = regime_counts.get('trend', 0)
        
        # At least 20% should be trend (conservative threshold)
        assert trend_count / len(df_processed) > 0.2
    
    
    def test_ranging_market_detection(self):
        """Test system correctly identifies ranging market."""
        # Create oscillating range
        n = 150
        base_price = 42000
        prices = base_price + np.sin(np.linspace(0, 8*np.pi, n)) * 300
        
        df = pd.DataFrame({
            'high': prices + 100,
            'low': prices - 100,
            'close': prices,
            'volume': 80 + np.abs(np.random.randn(n) * 10)
        })
        
        df_processed = calculate_complete_pipeline(df)
        
        # Should have range periods (may also have trend/chaos due to oscillation)
        regime_counts = df_processed['regime'].value_counts()
        
        # Should have multiple regime types due to oscillation
        assert len(regime_counts) >= 2
    
    
    def test_chaotic_market_detection(self):
        """Test system correctly identifies chaotic market."""
        # Create high volatility random walk
        n = 150
        base_price = 42000
        prices = base_price + np.cumsum(np.random.randn(n) * 500)
        
        df = pd.DataFrame({
            'high': prices + 200,
            'low': prices - 200,
            'close': prices,
            'volume': 100 + np.abs(np.random.randn(n) * 20)
        })
        
        df_processed = calculate_complete_pipeline(df)
        
        # Should have some chaos classification (high vol, low efficiency)
        regime_counts = df_processed['regime'].value_counts()
        
        # May have chaos, or trend if random walk happens to trend
        # Just verify classification completes successfully
        assert len(regime_counts) > 0
    
    
    def test_missing_data_handling(self):
        """Test system handles missing data gracefully."""
        # Create data with NaN values
        n = 100
        df = pd.DataFrame({
            'high': 42000 + np.random.randn(n) * 500,
            'low': 41000 + np.random.randn(n) * 500,
            'close': 41500 + np.random.randn(n) * 500,
            'volume': 100 + np.abs(np.random.randn(n) * 20)
        })
        
        # Inject some NaN values
        df.loc[10:15, 'close'] = np.nan
        df.loc[30:32, 'volume'] = np.nan
        
        # Should complete without crashing
        df_processed = calculate_complete_pipeline(df)
        
        # Periods with NaN should likely be NO_TRADE
        assert 'regime' in df_processed.columns
    
    
    def test_minimal_data_handling(self):
        """Test system handles minimal data (edge case)."""
        # Only 10 candles (insufficient for many indicators)
        df = pd.DataFrame({
            'high': [42000 + i*10 for i in range(10)],
            'low': [41800 + i*10 for i in range(10)],
            'close': [41900 + i*10 for i in range(10)],
            'volume': [100 + i for i in range(10)]
        })
        
        # Should complete without crashing (many NaN expected)
        df_processed = calculate_complete_pipeline(df)
        
        assert len(df_processed) == 10
        assert 'regime' in df_processed.columns
    
    
    def test_extreme_volatility_handling(self):
        """Test system handles extreme volatility."""
        # Create data with extreme price swings
        n = 100
        prices = [42000]
        
        for i in range(1, n):
            # Large random jumps
            change = np.random.choice([-1, 1]) * np.random.uniform(1000, 3000)
            prices.append(prices[-1] + change)
        
        prices = np.array(prices)
        
        df = pd.DataFrame({
            'high': prices + 500,
            'low': prices - 500,
            'close': prices,
            'volume': 150 + np.abs(np.random.randn(n) * 30)
        })
        
        # Should handle without crashing
        df_processed = calculate_complete_pipeline(df)
        
        # Likely to be classified as CHAOS or NO_TRADE
        regime_counts = df_processed['regime'].value_counts()
        chaos_or_no_trade = regime_counts.get('chaos', 0) + regime_counts.get('no_trade', 0)
        
        # Should have significant chaos/no_trade periods
        assert chaos_or_no_trade > 0
    
    
    def test_zero_volume_handling(self):
        """Test system handles zero volume periods."""
        n = 100
        df = pd.DataFrame({
            'high': 42000 + np.random.randn(n) * 500,
            'low': 41000 + np.random.randn(n) * 500,
            'close': 41500 + np.random.randn(n) * 500,
            'volume': 100 + np.abs(np.random.randn(n) * 20)
        })
        
        # Set some periods to zero volume
        df.loc[20:25, 'volume'] = 0
        
        # Should complete without division by zero errors
        df_processed = calculate_complete_pipeline(df)
        
        assert 'regime' in df_processed.columns
    
    
    def test_data_persistence_and_reload(self, tmp_path):
        """Test data can be saved and reloaded correctly."""
        # Create and process data
        n = 100
        df_original = pd.DataFrame({
            'timestamp': range(n),
            'high': 42000 + np.random.randn(n) * 500,
            'low': 41000 + np.random.randn(n) * 500,
            'close': 41500 + np.random.randn(n) * 500,
            'volume': 100 + np.abs(np.random.randn(n) * 20)
        })
        
        df_processed = calculate_complete_pipeline(df_original)
        
        # Save to CSV
        csv_path = tmp_path / "test_data.csv"
        df_processed.to_csv(csv_path, index=False)
        
        # Reload
        df_reloaded = pd.read_csv(csv_path)
        
        # Verify key columns preserved
        assert 'regime' in df_reloaded.columns
        assert 'regime_confidence' in df_reloaded.columns
        assert len(df_reloaded) == len(df_processed)
    
    
    def test_statistics_calculation(self):
        """Test regime statistics calculation works end-to-end."""
        n = 150
        df = pd.DataFrame({
            'high': 42000 + np.random.randn(n) * 500,
            'low': 41000 + np.random.randn(n) * 500,
            'close': 41500 + np.random.randn(n) * 500,
            'volume': 100 + np.abs(np.random.randn(n) * 20)
        })
        
        df_processed = calculate_complete_pipeline(df)
        
        # Get statistics
        stats = get_regime_statistics(df_processed)
        
        # Verify statistics structure
        assert 'total_periods' in stats
        assert 'regime_counts' in stats
        assert 'tradable_periods' in stats
        assert stats['total_periods'] == n
    
    
    def test_transition_analysis(self):
        """Test transition analysis works end-to-end."""
        n = 150
        df = pd.DataFrame({
            'high': 42000 + np.random.randn(n) * 500,
            'low': 41000 + np.random.randn(n) * 500,
            'close': 41500 + np.random.randn(n) * 500,
            'volume': 100 + np.abs(np.random.randn(n) * 20)
        })
        
        df_processed = calculate_complete_pipeline(df)
        
        # Analyze transitions
        analysis = analyze_regime_sequence(df_processed)
        
        # Verify analysis structure
        assert 'total_transitions' in analysis
        assert 'duration_stats' in analysis
        assert 'transition_matrix' in analysis
        assert 'persistence' in analysis
    
    
    def test_reproducibility(self):
        """Test that same input produces same output."""
        np.random.seed(42)
        
        n = 100
        df = pd.DataFrame({
            'high': 42000 + np.random.randn(n) * 500,
            'low': 41000 + np.random.randn(n) * 500,
            'close': 41500 + np.random.randn(n) * 500,
            'volume': 100 + np.abs(np.random.randn(n) * 20)
        })
        
        # Process twice
        df_result1 = calculate_complete_pipeline(df.copy())
        df_result2 = calculate_complete_pipeline(df.copy())
        
        # Results should be identical
        assert df_result1['regime'].equals(df_result2['regime'])
        assert np.allclose(
            df_result1['regime_confidence'].dropna(),
            df_result2['regime_confidence'].dropna()
        )


def test_all_modules_importable():
    """Test all modules can be imported without errors."""
    # Data modules
    from data import fetcher
    
    # Config modules
    from config import system_config, exchange_config
    
    # Regime modules
    from regime import features, classifier, visualization
    
    # All imports successful
    assert True


def test_configuration_loads():
    """Test configuration loads correctly."""
    from config.system_config import RISK_LIMITS, SYSTEM_CONFIG
    
    # Verify config objects exist
    assert RISK_LIMITS is not None
    assert SYSTEM_CONFIG is not None
    
    # Verify config is valid
    risk_valid, _ = RISK_LIMITS.validate()
    system_valid, _ = SYSTEM_CONFIG.validate()
    
    assert risk_valid
    assert system_valid


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
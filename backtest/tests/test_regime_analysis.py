# backtest/tests/test_regime_analysis.py
"""
Tests for regime-based performance analysis.
"""

import pytest
from datetime import datetime
from backtest.regime_analysis import RegimeAnalyzer
from backtest.trade import create_trade


class TestRegimeAnalyzer:
    """Test regime analysis functionality."""
    
    def test_empty_trades(self):
        """Test analysis with empty trade list."""
        analyzer = RegimeAnalyzer()
        stats = analyzer.analyze_trades([])
        
        assert stats['overall']['trades'] == 0
        assert stats['by_entry_regime'] == {}
        assert stats['by_exit_regime'] == {}
    
    def test_single_trade_analysis(self):
        """Test analysis with single trade."""
        analyzer = RegimeAnalyzer()
        
        trades = [
            create_trade(
                "W1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
            )
        ]
        
        stats = analyzer.analyze_trades(trades)
        
        assert stats['overall']['trades'] == 1
        assert stats['overall']['wins'] == 1
        assert stats['overall']['win_rate'] == 1.0
        
        # Check entry regime stats
        assert 'trend' in stats['by_entry_regime']
        assert stats['by_entry_regime']['trend']['trades'] == 1
        assert stats['by_entry_regime']['trend']['wins'] == 1
        
        # Check exit regime stats
        assert 'trend' in stats['by_exit_regime']
        
        # Check transition
        assert 'trend→trend' in stats['by_regime_transition']
    
    def test_multiple_regimes(self):
        """Test analysis with trades in different regimes."""
        analyzer = RegimeAnalyzer()
        
        trades = [
            create_trade("W1", datetime(2024, 1, 1), 42000, 'trend',
                        datetime(2024, 1, 2), 42500, 'trend', 'exit', 250),
            create_trade("L1", datetime(2024, 1, 3), 42500, 'trend',
                        datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250),
            create_trade("W2", datetime(2024, 1, 5), 41500, 'range',
                        datetime(2024, 1, 6), 42000, 'trend', 'exit', 250),
        ]
        
        stats = analyzer.analyze_trades(trades)
        
        # Check all regimes captured
        assert 'trend' in stats['by_entry_regime']
        assert 'range' in stats['by_entry_regime']
        
        assert 'trend' in stats['by_exit_regime']
        assert 'range' in stats['by_exit_regime']
        
        # Check transitions
        assert 'trend→trend' in stats['by_regime_transition']
        assert 'trend→range' in stats['by_regime_transition']
        assert 'range→trend' in stats['by_regime_transition']
        
        # Verify counts
        entry_trend = stats['by_entry_regime']['trend']
        assert entry_trend['trades'] == 2
        assert entry_trend['wins'] == 1
        assert entry_trend['losses'] == 1
        
        entry_range = stats['by_entry_regime']['range']
        assert entry_range['trades'] == 1
        assert entry_range['wins'] == 1
    
    def test_derived_metrics_calculation(self):
        """Test calculation of derived metrics."""
        analyzer = RegimeAnalyzer()
        
        trades = [
            create_trade("W1", datetime(2024, 1, 1), 42000, 'trend',
                        datetime(2024, 1, 2), 42500, 'trend', 'exit', 250),
            create_trade("L1", datetime(2024, 1, 3), 42500, 'trend',
                        datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250),
        ]
        
        stats = analyzer.analyze_trades(trades)
        
        # Check derived metrics exist
        overall = stats['overall']
        assert 'win_rate' in overall
        assert 'avg_pnl' in overall
        assert 'avg_win' in overall
        assert 'avg_loss' in overall
        assert 'profit_factor' in overall
        assert 'expectancy' in overall
        
        # Check calculations
        assert overall['win_rate'] == 0.5
        assert overall['trades'] == 2
    
    def test_duration_calculation(self):
        """Test trade duration tracking."""
        analyzer = RegimeAnalyzer()
        
        trades = [
            create_trade("T1", datetime(2024, 1, 1, 10, 0), 42000, 'trend',
                        datetime(2024, 1, 1, 14, 0), 42500, 'trend', 'exit', 250),  # 4 hours
            create_trade("T2", datetime(2024, 1, 2, 10, 0), 42500, 'trend',
                        datetime(2024, 1, 2, 12, 0), 42600, 'trend', 'exit', 250),  # 2 hours
        ]
        
        stats = analyzer.analyze_trades(trades)
        
        overall = stats['overall']
        assert 'avg_duration' in overall
        assert 'median_duration' in overall
        
        # Average should be 3 hours
        assert overall['avg_duration'] == 3.0
        assert len(overall['durations']) == 2
    
    def test_largest_win_loss(self):
        """Test tracking of largest win and loss."""
        analyzer = RegimeAnalyzer()
        
        trades = [
            create_trade("W1", datetime(2024, 1, 1), 42000, 'trend',
                        datetime(2024, 1, 2), 42500, 'trend', 'exit', 250),  # ~2.6 profit
            create_trade("W2", datetime(2024, 1, 3), 42000, 'trend',
                        datetime(2024, 1, 4), 42200, 'trend', 'exit', 250),  # ~1.0 profit
            create_trade("L1", datetime(2024, 1, 5), 42200, 'trend',
                        datetime(2024, 1, 5), 41160, 'range', 'stop_loss', 250),  # ~-5.8 loss
        ]
        
        stats = analyzer.analyze_trades(trades)
        
        overall = stats['overall']
        assert overall['largest_win'] > 0
        assert overall['largest_loss'] < 0
        
        # Largest win should be from first trade (~2.6)
        # Largest loss should be from third trade (~-5.8)
        assert overall['largest_win'] > overall['avg_pnl']
        assert overall['largest_loss'] < overall['avg_pnl']


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
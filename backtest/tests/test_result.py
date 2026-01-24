"""
Tests for BacktestResult.
"""

import pytest
from datetime import datetime, timedelta
from backtest.result import BacktestResult
from backtest.trade import create_trade


class TestBacktestResult:
    """Test BacktestResult dataclass."""
    
    def test_result_creation(self):
        """Test creating result with trades."""
        trades = [
            create_trade(
                "T1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
            ),
            create_trade(
                "T2", datetime(2024, 1, 3), 42500, 'trend',
                datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250
            ),
        ]
        
        result = BacktestResult(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
            initial_capital=500,
            final_capital=502.5,
            trades=trades
        )
        
        assert result.total_trades == 2
        assert result.winning_trades == 1
        assert result.losing_trades == 1
    
    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        trades = [
            create_trade(
                "W1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
            ),
            create_trade(
                "W2", datetime(2024, 1, 3), 42000, 'trend',
                datetime(2024, 1, 4), 42500, 'trend', 'exit', 250
            ),
            create_trade(
                "L1", datetime(2024, 1, 5), 42000, 'trend',
                datetime(2024, 1, 5), 41160, 'range', 'stop_loss', 250
            ),
        ]
        
        result = BacktestResult(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
            initial_capital=500,
            final_capital=505,
            trades=trades
        )
        
        # 2 wins out of 3 = 66.67%
        assert result.win_rate == pytest.approx(0.667, abs=0.01)
    
    def test_average_win_loss(self):
        """Test average win/loss calculation."""
        trades = [
            create_trade(
                "W1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42840, 'trend', 'exit', 250  # ~5 win
            ),
            create_trade(
                "L1", datetime(2024, 1, 3), 42000, 'trend',
                datetime(2024, 1, 3), 41160, 'range', 'stop_loss', 250  # ~-5 loss
            ),
        ]
        
        result = BacktestResult(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
            initial_capital=500,
            final_capital=500,
            trades=trades
        )
        
        assert result.average_win > 0
        assert result.average_loss < 0
    
    def test_expectancy_calculation(self):
        """Test expectancy calculation."""
        trades = [
            create_trade(
                "W1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
            ),
            create_trade(
                "L1", datetime(2024, 1, 3), 42000, 'trend',
                datetime(2024, 1, 3), 41160, 'range', 'stop_loss', 250
            ),
        ]
        
        result = BacktestResult(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
            initial_capital=500,
            final_capital=500,
            trades=trades
        )
        
        # Expectancy = average PnL per trade
        total_pnl = sum(t.pnl for t in trades)
        expected_expectancy = total_pnl / len(trades)
        
        assert result.expectancy == pytest.approx(expected_expectancy, abs=0.1)
    
    def test_get_summary(self):
        """Test summary dictionary generation."""
        result = BacktestResult(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 7),
            initial_capital=500,
            final_capital=510,
            trades=[]
        )
        
        summary = result.get_summary()
        
        assert 'period' in summary
        assert 'capital' in summary
        assert 'trades' in summary
        assert summary['capital']['return_pct'] == 2.0  # 10/500 = 2%


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
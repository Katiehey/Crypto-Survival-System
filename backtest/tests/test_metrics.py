"""
Tests for performance metrics calculations.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backtest.metrics import PerformanceMetrics
from backtest.trade import create_trade


class TestSharpeRatio:
    """Test Sharpe ratio calculation."""
    
    def test_sharpe_with_positive_returns(self):
        """Test Sharpe with positive returns."""
        returns = pd.Series([0.01, 0.02, 0.015, 0.01, 0.02])
        
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
        
        # Should be positive
        assert sharpe > 0
    
    def test_sharpe_with_negative_returns(self):
        """Test Sharpe with negative returns."""
        returns = pd.Series([-0.01, -0.02, -0.015, -0.01])
        
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
        
        # Should be negative
        assert sharpe < 0
    
    def test_sharpe_with_zero_volatility(self):
        """Test Sharpe with zero volatility returns."""
        returns = pd.Series([0.01, 0.01, 0.01, 0.01])
        
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
        
        # Zero std = zero Sharpe
        assert sharpe == 0.0
    
    def test_sharpe_with_insufficient_data(self):
        """Test Sharpe with insufficient data."""
        returns = pd.Series([0.01])
        
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
        
        assert sharpe == 0.0


class TestMaxDrawdown:
    """Test maximum drawdown calculation."""
    
    def test_max_drawdown_simple(self):
        """Test max drawdown with simple decline."""
        equity = pd.Series([100, 110, 105, 95, 100, 115])
        
        max_dd, duration, start, end = PerformanceMetrics.max_drawdown(equity)
        
        # Peak was 110 (index 1), trough was 95 (index 3)
        # Drawdown = (95 - 110) / 110 = -13.64%
        assert max_dd == pytest.approx(13.64, abs=0.1)
        assert duration > 0
    
    def test_max_drawdown_no_decline(self):
        """Test max drawdown with only gains."""
        equity = pd.Series([100, 110, 120, 130])
        
        max_dd, duration, start, end = PerformanceMetrics.max_drawdown(equity)
        
        # No drawdown
        assert max_dd == 0.0
    
    def test_max_drawdown_all_decline(self):
        """Test max drawdown with continuous decline."""
        equity = pd.Series([100, 90, 80, 70])
        
        max_dd, duration, start, end = PerformanceMetrics.max_drawdown(equity)
        
        # Max drawdown from 100 to 70 = 30%
        assert max_dd == pytest.approx(30.0, abs=0.1)


class TestProfitFactor:
    """Test profit factor calculation."""
    
    def test_profit_factor_positive(self):
        """Test profit factor with wins > losses."""
        trades = [
            create_trade(
                "W1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
            ),
            create_trade(
                "L1", datetime(2024, 1, 3), 42000, 'trend',
                datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250
            ),
        ]
        
        pf = PerformanceMetrics.profit_factor(trades)
        
        # More wins than losses = PF > 1
        assert pf > 0
    
    def test_profit_factor_no_losses(self):
        """Test profit factor with only wins."""
        trades = [
            create_trade(
                "W1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
            ),
        ]
        
        pf = PerformanceMetrics.profit_factor(trades)
        
        # No losses = infinite PF
        assert pf == float('inf')
    
    def test_profit_factor_no_wins(self):
        """Test profit factor with only losses."""
        trades = [
            create_trade(
                "L1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 1), 41160, 'range', 'stop_loss', 250
            ),
        ]
        
        pf = PerformanceMetrics.profit_factor(trades)
        
        # No wins = 0 PF
        assert pf == 0.0


class TestExpectancy:
    """Test expectancy calculation."""
    
    def test_expectancy_positive(self):
        """Test expectancy with positive average."""
        trades = [
            create_trade(
                "W1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
            ),
            create_trade(
                "W2", datetime(2024, 1, 3), 42000, 'trend',
                datetime(2024, 1, 4), 42500, 'trend', 'exit', 250
            ),
        ]
        
        exp = PerformanceMetrics.expectancy(trades)
        
        # Both winners = positive expectancy
        assert exp > 0
    
    def test_expectancy_negative(self):
        """Test expectancy with negative average."""
        trades = [
            create_trade(
                "L1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 1), 41160, 'range', 'stop_loss', 250
            ),
            create_trade(
                "L2", datetime(2024, 1, 2), 42000, 'trend',
                datetime(2024, 1, 2), 41160, 'range', 'stop_loss', 250
            ),
        ]
        
        exp = PerformanceMetrics.expectancy(trades)
        
        # Both losers = negative expectancy
        assert exp < 0


class TestWinRate:
    """Test win rate calculation."""
    
    def test_win_rate_50_percent(self):
        """Test win rate with 50% winners."""
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
        
        win_rate = PerformanceMetrics.win_rate(trades)
        
        assert win_rate == 0.5
    
    def test_win_rate_100_percent(self):
        """Test win rate with all winners."""
        trades = [
            create_trade(
                "W1", datetime(2024, 1, 1), 42000, 'trend',
                datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
            ),
        ]
        
        win_rate = PerformanceMetrics.win_rate(trades)
        
        assert win_rate == 1.0


class TestConsecutiveWinsLosses:
    """Test consecutive wins/losses calculation."""
    
    def test_consecutive_wins(self):
        """Test max consecutive wins."""
        trades = [
            create_trade(f"W{i}", datetime(2024, 1, i), 42000, 'trend',
                        datetime(2024, 1, i+1), 42500, 'trend', 'exit', 250)
            for i in range(1, 4)  # 3 consecutive wins
        ]
        
        max_wins, max_losses = PerformanceMetrics.consecutive_wins_losses(trades)
        
        assert max_wins == 3
        assert max_losses == 0
    
    def test_consecutive_losses(self):
        """Test max consecutive losses."""
        trades = [
            create_trade(f"L{i}", datetime(2024, 1, i), 42000, 'trend',
                        datetime(2024, 1, i), 41160, 'range', 'stop_loss', 250)
            for i in range(1, 3)  # 2 consecutive losses
        ]
        
        max_wins, max_losses = PerformanceMetrics.consecutive_wins_losses(trades)
        
        assert max_wins == 0
        assert max_losses == 2


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
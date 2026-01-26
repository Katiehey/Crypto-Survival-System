# backtest/tests/test_advanced_metrics.py
"""
Tests for advanced performance metrics.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from backtest.metrics import PerformanceMetrics
from backtest.trade import create_trade


class TestAdvancedMetrics:
    """Test advanced performance metrics."""
    
    def test_calmar_ratio_positive(self):
        """Test Calmar ratio with positive return and drawdown."""
        ratio = PerformanceMetrics.calmar_ratio(
            total_return_pct=20.0,  # 20% return
            max_drawdown_pct=-10.0  # 10% drawdown
        )
        
        # Should be 2.0 (20/10)
        assert ratio == 2.0
    
    def test_calmar_ratio_zero_drawdown(self):
        """Test Calmar ratio with zero drawdown."""
        ratio = PerformanceMetrics.calmar_ratio(
            total_return_pct=10.0,
            max_drawdown_pct=0.0
        )
        
        assert ratio == 0.0
    
    def test_sortino_ratio(self):
        """Test Sortino ratio calculation."""
        # Create returns with more downside than upside
        returns = pd.Series([0.01, -0.02, 0.015, -0.01, 0.02, -0.03])
        
        sortino = PerformanceMetrics.sortino_ratio(returns)
        
        # Should be a reasonable number
        assert isinstance(sortino, float)
    
    def test_sortino_no_downside(self):
        """Test Sortino ratio with no downside returns."""
        returns = pd.Series([0.01, 0.02, 0.015, 0.01])
        
        sortino = PerformanceMetrics.sortino_ratio(returns)
        
        # Should be infinite (no downside risk)
        assert sortino == float('inf')
    
    def test_value_at_risk(self):
        """Test Value at Risk calculation."""
        np.random.seed(42)
        returns = pd.Series(np.random.randn(100) * 0.01)  # 1% daily volatility
        
        var_95 = PerformanceMetrics.value_at_risk(returns, 0.95)
        var_99 = PerformanceMetrics.value_at_risk(returns, 0.99)
        
        # VaR should be negative (loss)
        assert var_95 < 0
        assert var_99 < 0
        # 99% VaR should be more negative than 95% VaR
        assert var_99 <= var_95
    
    def test_expected_shortfall(self):
        """Test Expected Shortfall calculation."""
        np.random.seed(42)
        returns = pd.Series(np.random.randn(100) * 0.01)
        
        es = PerformanceMetrics.expected_shortfall(returns, 0.95)
        
        # ES should be more negative than VaR
        var = PerformanceMetrics.value_at_risk(returns, 0.95)
        assert es <= var
    
    def test_ulcer_index(self):
        """Test Ulcer Index calculation."""
        # Create equity curve with drawdowns
        equity = pd.Series([100, 105, 95, 100, 110, 90, 100])
        
        ulcer = PerformanceMetrics.ulcer_index(equity, period=3)
        
        # Should be positive
        assert ulcer > 0
    
    def test_recovery_factor(self):
        """Test Recovery Factor calculation."""
        factor = PerformanceMetrics.recovery_factor(
            total_return=1000.0,
            max_drawdown=-500.0
        )
        
        # Should be 2.0 (1000/500)
        assert factor == 2.0
    
    def test_recovery_factor_zero_drawdown(self):
        """Test Recovery Factor with zero drawdown."""
        factor = PerformanceMetrics.recovery_factor(
            total_return=1000.0,
            max_drawdown=0.0
        )
        
        # Should be infinite (positive return, no drawdown)
        assert factor == float('inf')
    
    def test_risk_of_ruin(self):
        """Test Risk of Ruin calculation."""
        ruin = PerformanceMetrics.risk_of_ruin(
            win_rate=0.6,
            avg_win=200.0,
            avg_loss=-100.0,
            risk_per_trade=100.0
        )
        
        # Should be between 0 and 1
        assert 0 <= ruin <= 1
    
    def test_kelly_criterion(self):
        """Test Kelly Criterion calculation."""
        kelly = PerformanceMetrics.kelly_criterion(
            win_rate=0.6,
            win_loss_ratio=2.0,
            capped=False  
        )
        
        # Kelly = 0.6 - (0.4/2) = 0.6 - 0.2 = 0.4
        assert kelly == pytest.approx(0.4, abs=0.01)
    
    def test_kelly_criterion_negative(self):
        """Test Kelly Criterion with negative expectation."""
        kelly = PerformanceMetrics.kelly_criterion(
            win_rate=0.4,
            win_loss_ratio=1.0  # Even win/loss
        )
        
        # Kelly = 0.4 - (0.6/1) = -0.2 -> capped at 0
        assert kelly == 0.0
    
    def test_calculate_all_advanced_metrics(self):
        """Test calculation of all advanced metrics."""
        # Create sample trades
        trades = [
            create_trade("W1", datetime(2024, 1, 1), 42000, 'trend',
                        datetime(2024, 1, 2), 42500, 'trend', 'exit', 250),
            create_trade("L1", datetime(2024, 1, 3), 42500, 'trend',
                        datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250),
            create_trade("W2", datetime(2024, 1, 5), 41500, 'range',
                        datetime(2024, 1, 6), 42000, 'trend', 'exit', 250),
        ]
        
        # Create equity and returns series
        equity = pd.Series([500.0, 502.6, 496.8, 499.5])
        returns = pd.Series([0.0, 0.0052, -0.0115, 0.0054])
        
        metrics = PerformanceMetrics.calculate_all_advanced_metrics(
            trades, equity, returns
        )
        
        # Should have all metrics
        expected_keys = [
            'calmar_ratio', 'sortino_ratio', 'value_at_risk_95',
            'expected_shortfall_95', 'ulcer_index', 'recovery_factor',
            'risk_of_ruin', 'kelly_criterion', 'gain_to_pain_ratio',
            'profit_per_day'
        ]
        
        for key in expected_keys:
            assert key in metrics
        
        # Values should be reasonable
        assert isinstance(metrics['calmar_ratio'], float)
        assert isinstance(metrics['sortino_ratio'], float)
        assert metrics['risk_of_ruin'] >= 0
    
    def test_empty_data_handling(self):
        """Test handling of empty data."""
        metrics = PerformanceMetrics.calculate_all_advanced_metrics(
            [], pd.Series([100]), pd.Series([0.0])
        )
        
        assert metrics == {}


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
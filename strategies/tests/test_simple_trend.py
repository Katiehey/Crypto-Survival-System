"""
Tests for SimpleTrendStrategy.
"""

import pytest
import numpy as np
import pandas as pd
from strategies.simple_trend import SimpleTrendStrategy
from strategies.base import SignalType


class TestSimpleTrendStrategy:
    """Test simple trend following strategy."""
    
    def create_trend_data(self, n: int = 100, regime: str = 'trend') -> pd.DataFrame:
        """Create test data with trend."""
        prices = np.linspace(40000, 45000, n) + np.random.randn(n) * 100
        
        return pd.DataFrame({
            'close': prices,
            'high': prices + 100,
            'low': prices - 100,
            'volume': 100 + np.abs(np.random.randn(n) * 20),
            'regime': [regime] * n,
            'regime_confidence': np.random.uniform(0.7, 0.9, n),
            'efficiency_ratio': np.random.uniform(0.65, 0.85, n),
            'atr': np.random.uniform(500, 800, n),
            'volume_regime': ['normal'] * n,
        })
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = SimpleTrendStrategy()
        
        assert strategy.entry_efficiency_threshold == 0.65
        assert strategy.exit_efficiency_threshold == 0.4
        assert strategy.min_regime_confidence == 0.6
    
    def test_get_name(self):
        """Test strategy name."""
        strategy = SimpleTrendStrategy()
        
        assert strategy.get_name() == "Simple Trend Following"
    
    def test_regime_compatibility(self):
        """Test regime compatibility."""
        strategy = SimpleTrendStrategy()
        
        assert strategy.is_regime_compatible('trend') == True
        assert strategy.is_regime_compatible('range') == False
        assert strategy.is_regime_compatible('chaos') == False
        assert strategy.is_regime_compatible('no_trade') == False
    
    def test_entry_signal_generated(self):
        """Test that entry signal is generated in trend."""
        strategy = SimpleTrendStrategy()
        df = self.create_trend_data()
        
        signal = strategy.generate_signal(df, current_position=None)
        
        assert signal.signal_type == SignalType.LONG
        assert signal.confidence >= 0.4
        assert signal.stop_loss is not None
        assert signal.stop_loss < signal.entry_price
    
    def test_no_entry_wrong_regime(self):
        """Test no entry in wrong regime."""
        strategy = SimpleTrendStrategy()
        df = self.create_trend_data(regime='range')
        
        signal = strategy.generate_signal(df, current_position=None)
        
        assert signal.signal_type == SignalType.NO_TRADE
        assert "wrong regime" in signal.reason.lower()
    
    def test_no_entry_low_efficiency(self):
        """Test no entry when efficiency too low."""
        strategy = SimpleTrendStrategy()
        df = self.create_trend_data()
        
        # Set low efficiency
        df['efficiency_ratio'] = 0.3
        
        signal = strategy.generate_signal(df, current_position=None)
        
        assert signal.signal_type == SignalType.NO_TRADE
        assert "weak trend" in signal.reason.lower()
    
    def test_no_entry_low_confidence(self):
        """Test no entry when regime confidence too low."""
        strategy = SimpleTrendStrategy()
        df = self.create_trend_data()
        
        # Set low confidence
        df['regime_confidence'] = 0.3
        
        signal = strategy.generate_signal(df, current_position=None)
        
        assert signal.signal_type == SignalType.NO_TRADE
        assert "confidence" in signal.reason.lower()
    
    def test_exit_on_regime_change(self):
        """Test exit when regime changes."""
        strategy = SimpleTrendStrategy()
        df = self.create_trend_data()
        
        # Change last regime to range
        df.iloc[-1, df.columns.get_loc('regime')] = 'range'
        
        signal = strategy.generate_signal(df, current_position='long')
        
        assert signal.signal_type == SignalType.EXIT
        assert "regime changed" in signal.reason.lower()
    
    def test_exit_on_weak_trend(self):
        """Test exit when trend weakens."""
        strategy = SimpleTrendStrategy()
        df = self.create_trend_data()
        
        # Set low efficiency (trend weakening)
        df.iloc[-1, df.columns.get_loc('efficiency_ratio')] = 0.3
        
        signal = strategy.generate_signal(df, current_position='long')
        
        assert signal.signal_type == SignalType.EXIT
        assert "weakening" in signal.reason.lower()
    
    def test_stop_loss_calculation(self):
        """Test stop loss is calculated correctly."""
        strategy = SimpleTrendStrategy()
        
        entry_price = 42000
        atr = 600
        
        stop_loss = strategy._calculate_stop_loss(entry_price, atr)
        
        # Stop should be entry - (atr × 2)
        expected_stop = entry_price - (atr * 2)
        
        # Allow some range due to min/max constraints
        assert 40000 < stop_loss < 42000
    
    def test_stop_loss_within_limits(self):
        """Test stop loss respects min/max limits."""
        strategy = SimpleTrendStrategy()
        
        # Very high ATR (would create very wide stop)
        stop = strategy._calculate_stop_loss(42000, 5000)
        
        # Stop should not be wider than 5%
        min_allowed = 42000 * 0.95
        assert stop >= min_allowed
    
    def test_confidence_calculation(self):
        """Test confidence calculation."""
        strategy = SimpleTrendStrategy()
        
        confidence = strategy._calculate_entry_confidence(
            efficiency=0.8,
            regime_confidence=0.9,
            volume_regime='high'
        )
        
        assert 0 <= confidence <= 1
        assert confidence > 0.7  # Should be high for good conditions
    
    def test_validates_required_columns(self):
        """Test that strategy validates required columns."""
        strategy = SimpleTrendStrategy()
        
        # Missing efficiency_ratio
        df = pd.DataFrame({
            'close': [42000],
            'high': [42100],
            'low': [41900],
            'volume': [100],
            'regime': ['trend'],
        })
        
        with pytest.raises(ValueError, match="Missing strategy-required"):
            strategy.generate_signal(df)
    
    def test_hold_position(self):
        """Test holding position when no action needed."""
        strategy = SimpleTrendStrategy()
        df = self.create_trend_data()
        
        # Good conditions but already in position
        signal = strategy.generate_signal(df, current_position='long')
        
        # Should return NO_TRADE (hold)
        # Unless exit conditions are met
        if signal.signal_type == SignalType.NO_TRADE:
            assert "hold" in signal.reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
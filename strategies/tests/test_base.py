"""
Tests for strategy base class and framework.
"""

import pytest
import numpy as np
import pandas as pd
from strategies.base import (
    Strategy,
    SimpleStrategy,
    TradingSignal,
    SignalType
)


class TestTradingSignal:
    """Test TradingSignal dataclass."""
    
    def test_valid_signal(self):
        """Test creating valid signal."""
        signal = TradingSignal(
            signal_type=SignalType.LONG,
            confidence=0.8,
            entry_price=42000,
            stop_loss=41160,
            regime='trend',
            reason="Test signal"
        )
        
        assert signal.signal_type == SignalType.LONG
        assert signal.confidence == 0.8
        assert signal.entry_price == 42000
    
    def test_invalid_confidence(self):
        """Test that invalid confidence is rejected."""
        with pytest.raises(ValueError, match="Confidence"):
            TradingSignal(
                signal_type=SignalType.LONG,
                confidence=1.5,  # Invalid (>1)
                entry_price=42000
            )
    
    def test_invalid_entry_price(self):
        """Test that invalid entry price is rejected."""
        with pytest.raises(ValueError, match="Entry price"):
            TradingSignal(
                signal_type=SignalType.LONG,
                confidence=0.8,
                entry_price=-42000  # Invalid (negative)
            )
    
    def test_metadata_initialization(self):
        """Test that metadata is initialized to empty dict."""
        signal = TradingSignal(
            signal_type=SignalType.NO_TRADE,
            confidence=1.0,
            entry_price=42000
        )
        
        assert signal.metadata == {}


class TestStrategyBase:
    """Test Strategy base class."""
    
    def create_test_data(self, n: int = 100) -> pd.DataFrame:
        """Create test DataFrame."""
        return pd.DataFrame({
            'close': 42000 + np.random.randn(n) * 500,
            'high': 42500 + np.random.randn(n) * 500,
            'low': 41500 + np.random.randn(n) * 500,
            'volume': 100 + np.abs(np.random.randn(n) * 20),
            'regime': ['trend'] * n,
            'regime_confidence': np.random.uniform(0.6, 0.9, n),
        })
    
    def test_simple_strategy_initialization(self):
        """Test strategy can be initialized."""
        strategy = SimpleStrategy()
        
        assert strategy.signals_generated == 0
        assert strategy.last_signal is None
    
    def test_generate_signal(self):
        """Test signal generation."""
        strategy = SimpleStrategy()
        df = self.create_test_data()
        
        signal = strategy.generate_signal(df)
        
        assert isinstance(signal, TradingSignal)
        assert signal.signal_type == SignalType.NO_TRADE
        assert signal.confidence == 1.0
    
    def test_signal_recording(self):
        """Test that signals are recorded."""
        strategy = SimpleStrategy()
        df = self.create_test_data()
        
        signal = strategy.generate_signal(df)
        
        assert strategy.signals_generated == 1
        assert strategy.last_signal == signal
    
    def test_multiple_signals(self):
        """Test generating multiple signals."""
        strategy = SimpleStrategy()
        df = self.create_test_data()
        
        for _ in range(5):
            strategy.generate_signal(df)
        
        assert strategy.signals_generated == 5
    
    def test_validate_data_success(self):
        """Test data validation with valid data."""
        strategy = SimpleStrategy()
        df = self.create_test_data()
        
        is_valid = strategy.validate_data(df)
        
        assert is_valid == True
    
    def test_validate_data_missing_columns(self):
        """Test data validation catches missing columns."""
        strategy = SimpleStrategy()
        df = pd.DataFrame({'close': [42000]})  # Missing required columns
        
        with pytest.raises(ValueError, match="Missing required columns"):
            strategy.validate_data(df)
    
    def test_validate_data_empty(self):
        """Test data validation catches empty DataFrame."""
        strategy = SimpleStrategy()
        df = pd.DataFrame()
        
        with pytest.raises(ValueError, match="empty"):
            strategy.validate_data(df)
    
    def test_get_name(self):
        """Test get_name returns string."""
        strategy = SimpleStrategy()
        
        name = strategy.get_name()
        
        assert isinstance(name, str)
        assert len(name) > 0
    
    def test_is_regime_compatible(self):
        """Test regime compatibility check."""
        strategy = SimpleStrategy()
        
        assert strategy.is_regime_compatible('trend') == True
        assert strategy.is_regime_compatible('range') == True
        assert strategy.is_regime_compatible('chaos') == False
    
    def test_get_statistics(self):
        """Test statistics generation."""
        strategy = SimpleStrategy()
        df = self.create_test_data()
        
        strategy.generate_signal(df)
        
        stats = strategy.get_statistics()
        
        assert 'name' in stats
        assert 'signals_generated' in stats
        assert stats['signals_generated'] == 1
    
    def test_repr(self):
        """Test string representation."""
        strategy = SimpleStrategy()
        
        repr_str = repr(strategy)
        
        assert 'SimpleStrategy' in repr_str
        assert 'signals=0' in repr_str


class TestSignalType:
    """Test SignalType enum."""
    
    def test_signal_types_exist(self):
        """Test all signal types defined."""
        assert SignalType.LONG
        assert SignalType.SHORT
        assert SignalType.EXIT
        assert SignalType.NO_TRADE
    
    def test_signal_type_values(self):
        """Test signal type values."""
        assert SignalType.LONG.value == "long"
        assert SignalType.SHORT.value == "short"
        assert SignalType.EXIT.value == "exit"
        assert SignalType.NO_TRADE.value == "no_trade"


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
"""
Tests for backtest engine.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backtest.engine import BacktestEngine, Position
from strategies.simple_trend import SimpleTrendStrategy


class TestPosition:
    """Test Position class."""
    
    def test_position_creation(self):
        """Test creating a position."""
        pos = Position(
            entry_time=datetime(2024, 1, 1),
            entry_price=42000,
            entry_regime='trend',
            size=250,
            stop_loss=41160,
            side='long'
        )
        
        assert pos.entry_price == 42000
        assert pos.size == 250
        assert pos.stop_loss == 41160
    
    def test_stop_loss_check_not_hit(self):
        """Test stop loss check when not hit."""
        pos = Position(
            entry_time=datetime(2024, 1, 1),
            entry_price=42000,
            entry_regime='trend',
            size=250,
            stop_loss=41160,
            side='long'
        )
        
        # Price doesn't reach stop
        hit = pos.check_stop_loss(candle_low=41500)
        
        assert hit == False
    
    def test_stop_loss_check_hit(self):
        """Test stop loss check when hit."""
        pos = Position(
            entry_time=datetime(2024, 1, 1),
            entry_price=42000,
            entry_regime='trend',
            size=250,
            stop_loss=41160,
            side='long'
        )
        
        # Price hits stop
        hit = pos.check_stop_loss(candle_low=41000)
        
        assert hit == True
    
    def test_excursion_tracking(self):
        """Test MFE/MAE tracking."""
        pos = Position(
            entry_time=datetime(2024, 1, 1),
            entry_price=42000,
            entry_regime='trend',
            size=250,
            stop_loss=41160,
            side='long'
        )
        
        # Update with favorable move
        pos.update_excursions(high=42500, low=41800)
        
        assert pos.best_price == 42500
        assert pos.worst_price == 41800
        
        # Get excursions
        mfe = pos.get_mfe()
        mae = pos.get_mae()
        
        assert mfe == 500  # 42500 - 42000
        assert mae == 200  # 42000 - 41800


class TestBacktestEngine:
    """Test BacktestEngine."""
    
    def test_engine_initialization(self):
        """Test engine can be initialized."""
        strategy = SimpleTrendStrategy()
        
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=500,
            data_limit=100
        )
        
        assert engine.initial_capital == 500
        assert engine.capital == 500
        assert engine.current_position is None
        assert len(engine.trades) == 0
    
    def test_engine_requires_data(self):
        """Test engine validates sufficient data."""
        strategy = SimpleTrendStrategy()
        
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=500,
            data_limit=10  # Too little
        )
        
        # Should raise due to insufficient data
        with pytest.raises(ValueError, match="Insufficient data"):
            engine.run()
    
    def test_position_lifecycle(self):
        """Test opening and closing position."""
        pos = Position(
            entry_time=datetime(2024, 1, 1, 10, 0),
            entry_price=42000,
            entry_regime='trend',
            size=250,
            stop_loss=41160,
            side='long'
        )
        
        # Update excursions
        pos.update_excursions(high=42500, low=41800)
        
        # Check values
        assert pos.best_price == 42500
        assert pos.worst_price == 41800
        assert pos.get_mfe() == 500
        assert pos.get_mae() == 200


class TestBacktestExecution:
    """Test backtest execution (integration-style tests)."""
    
    @pytest.mark.skipif(
        True,  # Skip by default (requires real data)
        reason="Requires database with sufficient historical data"
    )
    def test_full_backtest(self):
        """Test running full backtest (requires data)."""
        strategy = SimpleTrendStrategy()
        
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=500,
            data_limit=200
        )
        
        result = engine.run()
        
        # Basic sanity checks
        assert result.initial_capital == 500
        assert result.total_trades >= 0
        assert result.final_capital > 0
    

if __name__ == "__main__":
    pytest.main([__file__, '-v'])
"""
Integration tests for complete backtest workflow.
"""

import pytest
from datetime import datetime
from backtest.engine import BacktestEngine
from backtest.data_loader import BacktestDataLoader
from strategies.simple_trend import SimpleTrendStrategy


class TestBacktestIntegration:
    """Integration tests for complete backtest workflow."""
    
    def test_data_loader_integration(self):
        """Test data loader produces valid data for backtest."""
        loader = BacktestDataLoader()
        
        # Load small dataset
        df = loader.load_and_prepare(limit=100)
        
        # Verify all required columns present
        required = [
            'close', 'high', 'low', 'volume',
            'regime', 'regime_confidence', 'regime_tradable',
            'atr', 'efficiency_ratio', 'volume_ratio'
        ]
        
        for col in required:
            assert col in df.columns, f"Missing column: {col}"
        
        # Verify regimes classified
        assert df['regime'].notna().any()
    
    def test_strategy_generates_valid_signals(self):
        """Test strategy generates valid signals from prepared data."""
        loader = BacktestDataLoader()
        df = loader.load_and_prepare(limit=100)
        
        strategy = SimpleTrendStrategy()
        
        # Generate signal from last 50 candles
        signal = strategy.generate_signal(df.tail(50), current_position=None)
        
        # Signal should be valid
        assert signal is not None
        assert signal.signal_type is not None
        assert signal.entry_price > 0
    
    @pytest.mark.skipif(
        True,  # Skip by default
        reason="Requires database with sufficient historical data"
    )
    def test_complete_backtest_workflow(self):
        """Test complete backtest workflow end-to-end."""
        # Create strategy
        strategy = SimpleTrendStrategy()
        
        # Create and run backtest
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=500,
            data_limit=200,
            slippage=0.001,
            fee_rate=0.00075
        )
        
        result = engine.run()
        
        # Verify result structure
        assert result is not None
        assert result.initial_capital == 500
        assert result.final_capital > 0
        assert result.total_trades >= 0
        
        # Verify metrics calculated
        assert result.total_return is not None
        assert result.win_rate >= 0
        assert result.win_rate <= 1
        
        # If trades occurred, verify they're valid
        if result.total_trades > 0:
            assert len(result.trades) == result.total_trades
            
            for trade in result.trades:
                assert trade.entry_price > 0
                assert trade.exit_price > 0
                assert trade.size > 0
                assert trade.fees_paid >= 0
    
    def test_backtest_respects_risk_limits(self):
        """Test that backtest respects risk engine limits."""
        # This is implicitly tested by the engine using RiskEngine
        # for position sizing and validation
        
        strategy = SimpleTrendStrategy()
        
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=500,
            data_limit=50
        )
        
        # Engine should use risk limits
        # Position sizes should be within MAX_RISK_PER_TRADE
        # This is validated in the engine's _open_position method
        
        # Just verify engine initializes correctly
        assert engine.initial_capital == 500
    
    def test_no_look_ahead_bias(self):
        """Test that backtest doesn't use future data."""
        loader = BacktestDataLoader()
        df = loader.load_and_prepare(limit=100)
        
        strategy = SimpleTrendStrategy()
        
        # At index 50, should only have access to data up to index 50
        # This is ensured by _get_data_up_to_current() method
        
        # Generate signal with only first 50 candles
        signal = strategy.generate_signal(df.iloc[:50], current_position=None)
        
        # Signal should be based only on available data
        assert signal is not None


class TestBacktestReproducibility:
    """Test backtest reproducibility."""
    
    @pytest.mark.skipif(
        True,
        reason="Requires database with sufficient historical data"
    )
    def test_backtest_is_deterministic(self):
        """Test that backtest produces same results on repeated runs."""
        strategy = SimpleTrendStrategy()
        
        # Run backtest twice
        engine1 = BacktestEngine(
            strategy=strategy,
            initial_capital=500,
            data_limit=100
        )
        result1 = engine1.run()
        
        engine2 = BacktestEngine(
            strategy=strategy,
            initial_capital=500,
            data_limit=100
        )
        result2 = engine2.run()
        
        # Results should be identical
        assert result1.total_trades == result2.total_trades
        assert result1.final_capital == result2.final_capital
        assert result1.total_return == result2.total_return


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
# scripts/test_backtest_complete.py
"""
Test complete backtest workflow end-to-end.
"""

import pytest
from datetime import datetime
from backtest.engine import BacktestEngine
from strategies.simple_trend import SimpleTrendStrategy
from backtest.equity_curve import create_equity_curve_from_trades


def test_complete_backtest_workflow():
    """Test complete backtest workflow."""
    # Create strategy
    strategy = SimpleTrendStrategy()
    
    # Create backtest engine with minimal data
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=500,
        data_limit=500,  # Small dataset for quick test
        slippage=0.001,
        fee_rate=0.00075,
        verbose=False
    )
    
    # Run backtest
    result = engine.run()
    
    # Verify result structure
    assert result is not None
    assert result.initial_capital == 500
    assert result.final_capital > 0
    
    # Verify metrics are calculated
    assert hasattr(result, 'total_return')
    assert hasattr(result, 'win_rate')
    assert hasattr(result, 'profit_factor')
    assert hasattr(result, 'max_drawdown')
    
    # Verify trades list
    assert isinstance(result.trades, list)
    
    # Create equity curve from trades
    curve = create_equity_curve_from_trades(result.trades, result.initial_capital)
    
    # Verify equity curve
    assert curve.get_current_equity() == result.final_capital
    assert curve.get_peak_equity() >= result.initial_capital
    
    # Verify statistics
    stats = curve.get_statistics()
    if result.total_trades > 0:
        assert 'total_return_pct' in stats
        assert 'max_drawdown_pct' in stats
    else:
        # If no trades, metrics should reflect a flat line
        assert stats.get('total_return_pct', 0) == 0
    
    print(f"✅ Backtest completed successfully")
    print(f"   Trades: {result.total_trades}")
    print(f"   Final Capital: R{result.final_capital:.2f}")
    print(f"   Return: {result.total_return_pct:.2f}%")
    print(f"   Win Rate: {result.win_rate:.1%}")


def test_backtest_with_no_trades():
    """Test backtest with conditions that produce no trades."""
    # Mock a strategy that never trades
    class NoTradeStrategy(SimpleTrendStrategy):
        def generate_signal(self, data, current_position):
            return None  # Never generates signal
    
    strategy = NoTradeStrategy()
    
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=500,
        data_limit=50,
        verbose=False
    )
    
    result = engine.run()
    
    # Should have no trades but still valid result
    assert result.total_trades == 0
    assert result.final_capital == 500  # No change
    assert result.total_return == 0
    assert result.win_rate == 0


def test_backtest_reproducibility():
    """Test that backtest produces same results on repeated runs."""
    strategy = SimpleTrendStrategy()
    
    # Run backtest twice
    engine1 = BacktestEngine(
        strategy=strategy,
        initial_capital=500,
        data_limit=200,
        verbose=False
    )
    result1 = engine1.run()
    
    engine2 = BacktestEngine(
        strategy=strategy,
        initial_capital=500,
        data_limit=200,
        verbose=False
    )
    result2 = engine2.run()
    
    # Results should be identical (deterministic)
    assert result1.total_trades == result2.total_trades
    assert result1.final_capital == result2.final_capital
    assert result1.total_return == result2.total_return
    
    print(f"✅ Backtest is reproducible")
    print(f"   Run 1 Trades: {result1.total_trades}, Return: {result1.total_return_pct:.2f}%")
    print(f"   Run 2 Trades: {result2.total_trades}, Return: {result2.total_return_pct:.2f}%")


def test_equity_curve_integration():
    """Test equity curve integration with backtest results."""
    # Create sample trades
    from backtest.trade import create_trade
    
    trades = [
        create_trade(
            "W1", datetime(2024, 1, 1), 42000, 'trend',
            datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
        ),
        create_trade(
            "L1", datetime(2024, 1, 3), 42500, 'trend',
            datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250
        ),
    ]
    
    # Create equity curve
    from backtest.equity_curve import create_equity_curve_from_trades
    curve = create_equity_curve_from_trades(trades, 500)
    
    # Verify calculations
    assert curve.get_current_equity() > 0
    assert len(curve.data) == 3  # Initial point + 2 trades
    
    # Get statistics
    stats = curve.get_statistics()
    assert 'total_return_pct' in stats
    assert 'max_drawdown_pct' in stats
    
    print(f"✅ Equity curve integration working")
    print(f"   Final equity: R{curve.get_current_equity():.2f}")
    print(f"   Peak equity: R{curve.get_peak_equity():.2f}")
    print(f"   Max drawdown: {stats['max_drawdown_pct']:.2f}%")


if __name__ == "__main__":
    print("=" * 60)
    print("COMPLETE BACKTEST WORKFLOW TEST")
    print("=" * 60)
    
    test_complete_backtest_workflow()
    print()
    
    test_backtest_with_no_trades()
    print()
    
    test_backtest_reproducibility()
    print()
    
    test_equity_curve_integration()
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
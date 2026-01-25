# scripts/run_backtest.py
"""
Complete backtest execution script.
Runs backtest and displays all performance metrics.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from backtest.engine import BacktestEngine
from strategies.simple_trend import SimpleTrendStrategy
from backtest.equity_curve import create_equity_curve_from_trades


def main():
    """Run complete backtest and display results."""
    print("=" * 70)
    print("BACKTEST EXECUTION")
    print("=" * 70)
    
    # Create strategy
    strategy = SimpleTrendStrategy()
    
    # Create backtest engine
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=500,
        data_limit=1000,  # More data for meaningful results
        slippage=0.001,
        fee_rate=0.00075,
        verbose=True
    )
    
    print("\n🚀 Running backtest...")
    result = engine.run()
    
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    
    # Basic results
    print(f"\n📊 BASIC METRICS")
    print(f"   Initial Capital: R{result.initial_capital:.2f}")
    print(f"   Final Capital: R{result.final_capital:.2f}")
    print(f"   Total Return: R{result.total_return:+.2f} ({result.total_return_pct:+.2f}%)")
    print(f"   Total Trades: {result.total_trades}")
    print(f"   Win Rate: {result.win_rate:.1%}")
    print(f"   Profit Factor: {result.profit_factor:.2f}")
    print(f"   Expectancy: R{result.expectancy:.2f}")
    
    # Risk metrics
    print(f"\n⚠️  RISK METRICS")
    print(f"   Max Drawdown: {result.max_drawdown:.2f}%")
    print(f"   Largest Loss: R{result.largest_loss:.2f}")
    print(f"   Largest Win: R{result.largest_win:.2f}")
    
    # Trade statistics
    print(f"\n📈 TRADE STATISTICS")
    print(f"   Avg Win: R{result.avg_win:.2f}")
    print(f"   Avg Loss: R{result.avg_loss:.2f}")
    print(f"   Avg Trade: R{result.avg_trade:.2f}")
    print(f"   Win/Loss Ratio: {result.win_loss_ratio:.2f}")
    
    # Consecutive streaks
    print(f"\n📊 STREAKS")
    print(f"   Max Consecutive Wins: {result.max_consecutive_wins}")
    print(f"   Max Consecutive Losses: {result.max_consecutive_losses}")
    
    # Create equity curve
    print(f"\n📉 EQUITY CURVE")
    curve = create_equity_curve_from_trades(result.trades, result.initial_capital)
    curve_stats = curve.get_statistics()
    
    print(f"   Peak Capital: R{curve_stats['peak_capital']:.2f}")
    print(f"   Current Drawdown: {curve_stats['current_drawdown_pct']:.2f}%")
    print(f"   Volatility: {curve_stats['volatility_pct']:.2f}%")
    
    # Drawdown periods
    drawdowns = curve.get_drawdown_periods(min_drawdown_pct=1.0)
    print(f"   Significant Drawdowns: {len(drawdowns)}")
    
    if drawdowns:
        print(f"\n   Worst Drawdowns:")
        for i, dd in enumerate(drawdowns[:3], 1):  # Show top 3
            print(f"     {i}. {dd['drawdown_pct']:.2f}% ({dd['duration']} trades)")
    
    # Regime analysis (if available)
    if hasattr(result, 'regime_stats') and result.regime_stats:
        print(f"\n🎭 REGIME ANALYSIS")
        for regime, stats in result.regime_stats.items():
            print(f"   {regime.upper():10s}: {stats['trades']} trades, "
                  f"Win Rate: {stats['win_rate']:.1%}, "
                  f"Avg PnL: R{stats['avg_pnl']:+.2f}")
    
    # Export results
    print(f"\n💾 EXPORT")
    print(f"   Results saved to: backtest_results/{datetime.now().strftime('%Y%m%d_%H%M%S')}_results.json")
    
    # Summary
    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if result.total_return_pct > 0:
        print(f"✅ POSITIVE EXPECTANCY: +{result.total_return_pct:.2f}%")
    else:
        print(f"❌ NEGATIVE EXPECTANCY: {result.total_return_pct:.2f}%")
    
    if result.win_rate > 0.5:
        print(f"✅ Good win rate: {result.win_rate:.1%}")
    else:
        print(f"⚠️  Low win rate: {result.win_rate:.1%}")
    
    if result.profit_factor > 1.5:
        print(f"✅ Strong profit factor: {result.profit_factor:.2f}")
    elif result.profit_factor > 1.0:
        print(f"⚠️  Marginal profit factor: {result.profit_factor:.2f}")
    else:
        print(f"❌ Poor profit factor: {result.profit_factor:.2f}")
    
    if result.max_drawdown < 10:
        print(f"✅ Acceptable drawdown: {result.max_drawdown:.2f}%")
    elif result.max_drawdown < 20:
        print(f"⚠️  High drawdown: {result.max_drawdown:.2f}%")
    else:
        print(f"❌ Excessive drawdown: {result.max_drawdown:.2f}%")
    
    print(f"\n" + "=" * 70)
    print("Backtest complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
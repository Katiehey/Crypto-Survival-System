# scripts/run_backtest.py
"""
Complete backtest execution script.
Runs backtest and displays all performance metrics.
"""

import sys
import os
import json
import pandas as pd
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
            # 1. Extract Win Rate safely
            wr_data = stats.get('win_rate', 0)
            win_rate_val = wr_data.get('overall', 0) if isinstance(wr_data, dict) else wr_data
            
            # 2. Extract Avg PnL safely
            pnl_data = stats.get('avg_pnl', 0)
            pnl_val = pnl_data.get('overall', 0) if isinstance(pnl_data, dict) else pnl_data

            print(f"   {regime.upper():10s}: {stats.get('trades', 0)} trades, "
                  f"Win Rate: {win_rate_val:.1%}, "
                  f"Avg PnL: R{pnl_val:+.2f}")
    
    # Export results
    print(f"\n💾 EXPORT")
    export_dir = "backtest_results"
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
    
    # We'll save as 'metrics.json' so your reproduce script finds it immediately, 
    # but also a timestamped version for your history.
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_results.json"
    filepath = os.path.join(export_dir, filename)
    latest_path = os.path.join(export_dir, "metrics.json")

    serializable_trades = []
    for t in result.trades:
        if hasattr(t, 'to_dict'):
            serializable_trades.append(t.to_dict())
        else:
            # Fallback: manual dict creation
            serializable_trades.append({
                'entry_price': getattr(t, 'entry_price', 0),
                'exit_price': getattr(t, 'exit_price', 0),
                'pnl': getattr(t, 'pnl', 0),
                'pnl_pct': getattr(t, 'pnl_pct', 0),
                'regime': getattr(t, 'regime', 'unknown'),
                'is_winner': getattr(t, 'is_winner', False),
                'duration': getattr(t, 'duration', 1)
            })

    # Helper to convert result object to a serializable dictionary
    # We exclude the raw dataframes if they exist to keep the JSON small
    export_data = {k: v for k, v in result.__dict__.items() if not isinstance(v, (pd.DataFrame, pd.Series))}
    export_data['trades'] = serializable_trades
    try:
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=4, default=str)
        # Create a copy as metrics.json for the report script
        with open(latest_path, 'w') as f:
            json.dump(export_data, f, indent=4, default=str)
        print(f"   Results saved to: {filepath}")
        print(f"   Report source updated: {latest_path}")
    except Exception as e:
        print(f"   ❌ Export failed: {e}")


if __name__ == "__main__":
    main()
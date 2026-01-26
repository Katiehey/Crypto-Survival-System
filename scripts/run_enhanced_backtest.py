# scripts/run_enhanced_backtest.py
"""
Enhanced backtest execution with visualizations and advanced metrics.
"""

import sys
import os
import json
from datetime import datetime
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backtest.visualization import BacktestVisualizer
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("⚠️  Visualization not available. Install matplotlib for plots.")

from backtest.engine import BacktestEngine
from strategies.simple_trend import SimpleTrendStrategy
from backtest.equity_curve import create_equity_curve_from_trades
from backtest.regime_analysis import RegimeAnalyzer


def run_enhanced_backtest():
    """Run enhanced backtest with all features."""
    print("=" * 80)
    print("ENHANCED BACKTEST EXECUTION")
    print("=" * 80)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create results directory
    results_dir = "backtest_results"
    plots_dir = os.path.join(results_dir, "plots", timestamp)
    os.makedirs(plots_dir, exist_ok=True)
    
    # 1. Create strategy
    print("\n1. 📊 Creating SimpleTrendStrategy...")
    strategy = SimpleTrendStrategy(
    entry_efficiency_threshold=0.55,
    exit_efficiency_threshold=-0.1,
    min_regime_confidence=0.80, # Lower confidence to get more entries
    stop_loss_atr_multiple=2.5,  # REDUCE THIS (e.g., from 3.0 to 1.8)
)
    
    # 2. Create backtest engine
    print("2. ⚙️  Creating BacktestEngine...")
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=500,
        data_limit=5000,  # Reasonable amount for testing
        slippage=0.001,
        fee_rate=0.00075,
        verbose=False  # Less verbose for cleaner output
    )
    
    # 3. Run backtest
    print("\n3. 🚀 Running backtest...")
    print("-" * 40)
    result = engine.run()
    print("-" * 40)
    
    if result.total_trades == 0:
        print("\n⚠️  No trades executed. Exiting.")
        return
    
    # 4. Create equity curve
    print("\n4. 📈 Creating equity curve...")
    equity_curve = create_equity_curve_from_trades(result.trades, result.initial_capital)
    equity_series = equity_curve.get_equity_series()
    
    # 5. Perform regime analysis
    print("5. 🎭 Analyzing regime performance...")
    regime_analyzer = RegimeAnalyzer()
    regime_stats = regime_analyzer.analyze_trades(result.trades)
    
    # 6. Generate visualizations
    if VISUALIZATION_AVAILABLE:
        print("\n6. 🎨 Generating visualizations...")
        visualizer = BacktestVisualizer(output_dir=plots_dir)
        visualizer.plot_all(
            equity_series, 
            result.trades,
            f"{timestamp}: "
        )
    else:
        print("\n6. ⏭️  Skipping visualizations (matplotlib not available)")
    
    # 7. Compile complete results with advanced metrics
    print("\n7. 📋 Compiling results with advanced metrics...")
    
    # Get advanced metrics
    advanced_metrics = result.advanced_metrics
    
    complete_results = {
        'metadata': {
            'timestamp': timestamp,
            'strategy': 'SimpleTrendStrategy',
            'initial_capital': result.initial_capital,
            'data_points': engine.data_limit,
            'period': f"{result.start_date} to {result.end_date}",
            'slippage': engine.slippage,
            'fee_rate': engine.fee_rate
        },
        'basic_metrics': {
            'final_capital': result.final_capital,
            'total_return': result.total_return,
            'total_return_pct': result.total_return_pct,
            'total_trades': result.total_trades,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'expectancy': result.expectancy,
            'sharpe_ratio': result.sharpe_ratio,
        },
        'risk_metrics': {
            'max_drawdown': result.max_drawdown,
            'largest_win': result.largest_win,
            'largest_loss': result.largest_loss,
            'avg_win': result.avg_win,
            'avg_loss': result.avg_loss,
            'avg_trade': result.avg_trade,
            'win_loss_ratio': result.win_loss_ratio,
            'max_consecutive_wins': result.max_consecutive_wins,
            'max_consecutive_losses': result.max_consecutive_losses,
        },
        'advanced_metrics': advanced_metrics,
        'equity_curve': {
            'peak_capital': equity_curve.get_peak_equity(),
            'current_drawdown_pct': equity_curve.get_statistics()['current_drawdown_pct'],
            'max_drawdown_pct': equity_curve.get_statistics()['max_drawdown_pct'],
            'volatility_pct': equity_curve.get_statistics()['volatility_pct'],
            'winning_periods': equity_curve.get_statistics()['winning_periods'],
            'losing_periods': equity_curve.get_statistics()['losing_periods'],
        },
        'regime_analysis': regime_stats,
        'files': {
            'plots_directory': plots_dir if VISUALIZATION_AVAILABLE else None,
            'equity_data': os.path.join(results_dir, f"{timestamp}_equity.csv"),
            'trades_data': os.path.join(results_dir, f"{timestamp}_trades.csv")
        }
    }
    
    # 8. Save data files
    print("\n8. 💾 Saving data files...")
    
    # Save equity data
    equity_df = equity_curve.to_dataframe()
    equity_file = os.path.join(results_dir, f"{timestamp}_equity.csv")
    equity_df.to_csv(equity_file, index=False)
    print(f"   Equity data: {equity_file}")
    
    # Save trades data
    trades_data = []
    for trade in result.trades:
        trades_data.append(trade.to_dict())
    
    trades_file = os.path.join(results_dir, f"{timestamp}_trades.csv")
    pd.DataFrame(trades_data).to_csv(trades_file, index=False)
    print(f"   Trades data: {trades_file}")
    
    # Save complete results
    results_file = os.path.join(results_dir, f"{timestamp}_complete_results.json")
    with open(results_file, 'w') as f:
        json.dump(complete_results, f, indent=2, default=str)
    print(f"   Complete results: {results_file}")
    
    # 9. Display executive summary
    print("\n" + "=" * 80)
    print("EXECUTIVE SUMMARY")
    print("=" * 80)
    
    # Performance scorecard
    print(f"\n📊 PERFORMANCE SCORECARD")
    print(f"   Return:         {result.total_return_pct:+.2f}%")
    print(f"   Win Rate:       {result.win_rate:.1%}")
    print(f"   Profit Factor:  {result.profit_factor:.2f}")
    print(f"   Sharpe Ratio:   {result.sharpe_ratio:.2f}")
    print(f"   Max Drawdown:   {result.max_drawdown:.2f}%")
    print(f"   Expectancy:     R{result.expectancy:.2f}")
    
    # Advanced metrics summary
    print(f"\n⚡ ADVANCED METRICS")
    print(f"   Calmar Ratio:   {advanced_metrics.get('calmar_ratio', 0):.2f}")
    print(f"   Sortino Ratio:  {advanced_metrics.get('sortino_ratio', 0):.2f}")
    print(f"   Ulcer Index:    {advanced_metrics.get('ulcer_index', 0):.3f}")
    print(f"   Risk of Ruin:   {advanced_metrics.get('risk_of_ruin', 0):.1%}")
    print(f"   Kelly Criterion:{advanced_metrics.get('kelly_criterion', 0):.1%}")
    
    # Regime performance
    print(f"\n🎭 REGIME PERFORMANCE")
    if regime_stats['by_entry_regime']:
        best_regime = max(
            regime_stats['by_entry_regime'].items(),
            key=lambda x: x[1]['avg_pnl'] if x[1]['trades'] > 0 else -float('inf')
        )
        worst_regime = min(
            regime_stats['by_entry_regime'].items(),
            key=lambda x: x[1]['avg_pnl'] if x[1]['trades'] > 0 else float('inf')
        )
        
        if best_regime[1]['trades'] > 0:
            print(f"   Best Regime:    {best_regime[0].upper():10s} "
                  f"(Avg PnL: R{best_regime[1]['avg_pnl']:+.2f})")
        if worst_regime[1]['trades'] > 0:
            print(f"   Worst Regime:   {worst_regime[0].upper():10s} "
                  f"(Avg PnL: R{worst_regime[1]['avg_pnl']:+.2f})")
    
    # Trading statistics
    print(f"\n📈 TRADING STATISTICS")
    print(f"   Total Trades:   {result.total_trades}")
    print(f"   Avg Trade:      R{result.avg_trade:.2f}")
    print(f"   Avg Win:        R{result.avg_win:.2f}")
    print(f"   Avg Loss:       R{result.avg_loss:.2f}")
    print(f"   Win/Loss Ratio: {result.win_loss_ratio:.2f}")
    
    # Recommendations
    print(f"\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    recommendations = []
    
    # Evaluate performance
    if result.total_return_pct > 10:
        recommendations.append("✅ Strong positive returns - consider paper trading")
    elif result.total_return_pct > 0:
        recommendations.append("⚠️  Marginal returns - needs optimization")
    else:
        recommendations.append("❌ Negative returns - strategy needs revision")
    
    if result.win_rate > 0.55:
        recommendations.append("✅ Good win rate - consistent performance")
    elif result.win_rate > 0.45:
        recommendations.append("⚠️  Moderate win rate - focus on risk management")
    else:
        recommendations.append("❌ Low win rate - improve entry timing")
    
    if result.profit_factor > 1.5:
        recommendations.append("✅ Excellent profit factor - winners > losers")
    elif result.profit_factor > 1.0:
        recommendations.append("⚠️  Marginal profit factor - barely profitable")
    else:
        recommendations.append("❌ Poor profit factor - losing money")
    
    if result.max_drawdown < 15:
        recommendations.append("✅ Acceptable drawdown - good risk management")
    elif result.max_drawdown < 25:
        recommendations.append("⚠️  High drawdown - increase stop losses")
    else:
        recommendations.append("❌ Excessive drawdown - reduce position sizes")
    
    if advanced_metrics.get('risk_of_ruin', 1) < 0.05:
        recommendations.append("✅ Low risk of ruin - sustainable strategy")
    elif advanced_metrics.get('risk_of_ruin', 1) < 0.20:
        recommendations.append("⚠️  Moderate risk of ruin - monitor closely")
    else:
        recommendations.append("❌ High risk of ruin - reduce position sizes")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. {rec}")
    
    # Next steps
    print(f"\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    
    print("""
    1. Review generated plots in: {}
    2. Analyze regime performance for optimization opportunities
    3. Run backtest with different parameters
    4. If results are positive, proceed to paper trading
    5. If results are negative, revise strategy logic
    """.format(plots_dir if VISUALIZATION_AVAILABLE else "N/A"))
    
    print(f"\n📁 All results saved to: {results_dir}/{timestamp}_*")
    print(f"\n" + "=" * 80)
    print("ENHANCED BACKTEST COMPLETE")
    print("=" * 80)
    
    return complete_results


if __name__ == "__main__":
    try:
        results = run_enhanced_backtest()
        print("\n✅ Enhanced backtest execution successful!")
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
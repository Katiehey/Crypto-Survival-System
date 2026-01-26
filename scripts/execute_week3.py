# scripts/execute_week3.py
"""
Execute Week 3 backtesting framework.
Runs complete backtest with all metrics and analysis.
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.engine import BacktestEngine
from strategies.simple_trend import SimpleTrendStrategy
from backtest.equity_curve import create_equity_curve_from_trades
from backtest.regime_analysis import RegimeAnalyzer


def run_complete_backtest():
    """Run complete backtest with all analysis."""
    print("=" * 80)
    print("WEEK 3: COMPLETE BACKTEST EXECUTION")
    print("=" * 80)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create results directory
    results_dir = "backtest_results"
    os.makedirs(results_dir, exist_ok=True)
    
    # 1. Create strategy
    print("\n1. 📊 Creating SimpleTrendStrategy...")
    strategy = SimpleTrendStrategy()
    
    # 2. Create backtest engine
    print("2. ⚙️  Creating BacktestEngine...")
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=500,
        data_limit=2000,  # More data for better statistics
        slippage=0.001,
        fee_rate=0.00075,
        verbose=True
    )
    
    # 3. Run backtest
    print("\n3. 🚀 Running backtest...")
    print("-" * 40)
    result = engine.run()
    print("-" * 40)
    
    # 4. Create equity curve
    print("\n4. 📈 Creating equity curve...")
    equity_curve = create_equity_curve_from_trades(result.trades, result.initial_capital)
    
    # 5. Perform regime analysis
    print("5. 🎭 Analyzing regime performance...")
    regime_analyzer = RegimeAnalyzer()
    regime_stats = regime_analyzer.analyze_trades(result.trades)
    
    # 6. Compile complete results
    print("6. 📋 Compiling results...")
    
    complete_results = {
        'metadata': {
            'timestamp': timestamp,
            'strategy': 'SimpleTrendStrategy',
            'initial_capital': result.initial_capital,
            'data_points': engine.data_limit,
            'slippage': engine.slippage,
            'fee_rate': engine.fee_rate
        },
        'performance_metrics': {
            'final_capital': result.final_capital,
            'total_return': result.total_return,
            'total_return_pct': result.total_return_pct,
            'total_trades': result.total_trades,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'expectancy': result.expectancy,
            'max_drawdown': result.max_drawdown,
            'largest_win': result.largest_win,
            'largest_loss': result.largest_loss,
            'avg_win': result.avg_win,
            'avg_loss': result.avg_loss,
            'avg_trade': result.avg_trade,
            'win_loss_ratio': result.win_loss_ratio,
            'max_consecutive_wins': result.max_consecutive_wins,
            'max_consecutive_losses': result.max_consecutive_losses,
            'sharpe_ratio': result.sharpe_ratio
        },
        'equity_curve': {
            'peak_capital': equity_curve.get_peak_equity(),
            'current_drawdown_pct': equity_curve.get_statistics()['current_drawdown_pct'],
            'max_drawdown_pct': equity_curve.get_statistics()['max_drawdown_pct'],
            'volatility_pct': equity_curve.get_statistics()['volatility_pct'],
            'total_points': len(equity_curve.data)
        },
        'regime_analysis': regime_stats,
        'trades': [
            {
                'trade_id': t.trade_id,
                'entry_time': t.entry_time.isoformat(),
                'exit_time': t.exit_time.isoformat(),
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'entry_regime': t.entry_regime,
                'exit_regime': t.exit_regime,
                'size': t.size,
                'pnl': t.pnl,
                'pnl_percent': t.pnl_percent,
                'exit_reason': t.exit_reason,
                'is_winner': t.is_winner
            }
            for t in result.trades
        ]
    }
    
    # 7. Save results
    results_file = os.path.join(results_dir, f"{timestamp}_complete_backtest.json")
    with open(results_file, 'w') as f:
        json.dump(complete_results, f, indent=2, default=str)
    
    # 8. Display summary
    print("\n" + "=" * 80)
    print("BACKTEST COMPLETE - SUMMARY")
    print("=" * 80)
    
    # Basic performance
    print(f"\n💰 CAPITAL")
    print(f"   Initial: R{result.initial_capital:.2f}")
    print(f"   Final: R{result.final_capital:.2f}")
    print(f"   Return: {result.total_return_pct:+.2f}%")
    
    print(f"\n📊 TRADES")
    print(f"   Total: {result.total_trades}")
    print(f"   Win Rate: {result.win_rate:.1%}")
    print(f"   Profit Factor: {result.profit_factor:.2f}")
    print(f"   Expectancy: R{result.expectancy:.2f}")
    
    print(f"\n⚠️  RISK")
    print(f"   Max Drawdown: {result.max_drawdown:.2f}%")
    print(f"   Largest Loss: R{result.largest_loss:.2f}")
    print(f"   Sharpe Ratio: {result.sharpe_ratio:.2f}")
    
    print(f"\n📈 EQUITY CURVE")
    equity_stats = equity_curve.get_statistics()
    print(f"   Peak: R{equity_stats['peak_capital']:.2f}")
    print(f"   Current Drawdown: {equity_stats['current_drawdown_pct']:.2f}%")
    print(f"   Volatility: {equity_stats['volatility_pct']:.2f}%")
    
    print(f"\n🎭 REGIME PERFORMANCE")
    if regime_stats['by_entry_regime']:
        for regime, stats in regime_stats['by_entry_regime'].items():
            if stats['trades'] > 0:
                print(f"   {regime.upper():10s}: {stats['trades']:2d} trades, "
                      f"Win: {stats['win_rate']:.1%}, "
                      f"Avg PnL: R{stats['avg_pnl']:+.2f}")
    
    # Performance evaluation
    print(f"\n" + "=" * 80)
    print("PERFORMANCE EVALUATION")
    print("=" * 80)
    
    evaluations = []
    
    # Positive expectancy
    if result.total_return_pct > 0:
        evaluations.append("✅ Positive total return")
    else:
        evaluations.append("❌ Negative total return")
    
    # Win rate
    if result.win_rate > 0.5:
        evaluations.append(f"✅ Good win rate ({result.win_rate:.1%})")
    elif result.win_rate > 0.4:
        evaluations.append(f"⚠️  Moderate win rate ({result.win_rate:.1%})")
    else:
        evaluations.append(f"❌ Low win rate ({result.win_rate:.1%})")
    
    # Profit factor
    if result.profit_factor > 1.5:
        evaluations.append(f"✅ Strong profit factor ({result.profit_factor:.2f})")
    elif result.profit_factor > 1.0:
        evaluations.append(f"⚠️  Marginal profit factor ({result.profit_factor:.2f})")
    else:
        evaluations.append(f"❌ Poor profit factor ({result.profit_factor:.2f})")
    
    # Drawdown
    if result.max_drawdown < 10:
        evaluations.append(f"✅ Acceptable drawdown ({result.max_drawdown:.2f}%)")
    elif result.max_drawdown < 20:
        evaluations.append(f"⚠️  High drawdown ({result.max_drawdown:.2f}%)")
    else:
        evaluations.append(f"❌ Excessive drawdown ({result.max_drawdown:.2f}%)")
    
    # Sharpe ratio
    if result.sharpe_ratio > 1.0:
        evaluations.append(f"✅ Good Sharpe ratio ({result.sharpe_ratio:.2f})")
    elif result.sharpe_ratio > 0.5:
        evaluations.append(f"⚠️  Moderate Sharpe ratio ({result.sharpe_ratio:.2f})")
    else:
        evaluations.append(f"❌ Poor Sharpe ratio ({result.sharpe_ratio:.2f})")
    
    for eval_item in evaluations:
        print(f"   {eval_item}")
    
    # Final recommendation
    print(f"\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    
    positive_factors = sum(1 for e in evaluations if e.startswith("✅"))
    warning_factors = sum(1 for e in evaluations if e.startswith("⚠️"))
    negative_factors = sum(1 for e in evaluations if e.startswith("❌"))
    
    if positive_factors >= 4 and negative_factors == 0:
        print("✅ STRONG - Strategy shows promising results")
        print("   Consider paper trading with micro-capital")
    elif positive_factors >= 3 and negative_factors <= 1:
        print("⚠️  MODERATE - Strategy needs improvement")
        print("   Optimize parameters before live trading")
    else:
        print("❌ WEAK - Strategy needs significant work")
        print("   Review logic and test with different parameters")
    
    print(f"\n📁 Results saved to: {results_file}")
    print(f"\n" + "=" * 80)
    print("WEEK 3 BACKTEST FRAMEWORK - COMPLETE")
    print("=" * 80)
    
    return complete_results


if __name__ == "__main__":
    try:
        results = run_complete_backtest()
        print("\n✅ Week 3 execution successful!")
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
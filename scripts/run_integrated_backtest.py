# scripts/run_integrated_backtest.py
"""
Fully integrated backtest execution with reporting.
"""

import sys
import os
import json
from datetime import datetime
import webbrowser

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.engine import BacktestEngine
from strategies.simple_trend import SimpleTrendStrategy
from backtest.equity_curve import create_equity_curve_from_trades
from backtest.regime_analysis import RegimeAnalyzer
from backtest.reporting import BacktestReporter


class IntegratedBacktest:
    """
    Fully integrated backtest execution system.
    
    Handles:
    - Strategy execution
    - Performance analysis
    - Visualization generation
    - Report creation
    """
    
    def __init__(
        self,
        initial_capital: float = 500,
        data_limit: int = 2000,
        slippage: float = 0.001,
        fee_rate: float = 0.00075
    ):
        """
        Initialize integrated backtest.
        
        Args:
            initial_capital: Starting capital
            data_limit: Number of candles to use
            slippage: Slippage percentage
            fee_rate: Trading fee rate
        """
        self.initial_capital = initial_capital
        self.data_limit = data_limit
        self.slippage = slippage
        self.fee_rate = fee_rate
        
        self.engine = None
        self.result = None
        self.equity_curve = None
        self.regime_stats = None
        self.report_file = None
        
        # Create results directory
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = f"backtest_results/{self.timestamp}"
        os.makedirs(self.results_dir, exist_ok=True)
    
    def run(self, strategy_class=None, verbose: bool = True) -> dict:
        """
        Run complete backtest.
        
        Args:
            strategy_class: Strategy class to use (defaults to SimpleTrendStrategy)
            verbose: Whether to print progress
            
        Returns:
            Dictionary with all results
        """
        if verbose:
            self._print_header()
        
        try:
            # 1. Setup
            if verbose:
                print("1. 🚀 Setting up backtest...")
            
            strategy = strategy_class() if strategy_class else SimpleTrendStrategy()
            
            self.engine = BacktestEngine(
                strategy=strategy,
                initial_capital=self.initial_capital,
                data_limit=self.data_limit,
                slippage=self.slippage,
                fee_rate=self.fee_rate,
                verbose=False
            )
            
            # 2. Execute backtest
            if verbose:
                print("2. ⚡ Executing backtest...")
            
            self.result = self.engine.run()
            
            if self.result.total_trades == 0:
                if verbose:
                    print("⚠️  No trades executed.")
                return self._compile_results()
            
            # 3. Analyze results
            if verbose:
                print("3. 📊 Analyzing results...")
            
            self.equity_curve = create_equity_curve_from_trades(
                self.result.trades, self.initial_capital
            )
            
            regime_analyzer = RegimeAnalyzer()
            self.regime_stats = regime_analyzer.analyze_trades(self.result.trades)
            
            # 4. Generate report
            if verbose:
                print("4. 📄 Generating report...")
            
            reporter = BacktestReporter(output_dir=self.results_dir)
            self.report_file = reporter.generate_report(
                self.result, self.equity_curve, self.regime_stats, self.timestamp
            )
            
            # 5. Save detailed results
            if verbose:
                print("5. 💾 Saving results...")
            
            self._save_detailed_results()
            
            # 6. Display summary
            if verbose:
                self._display_summary()
                print(f"\n✅ Backtest complete!")
                print(f"📁 Results saved to: {self.results_dir}/")
            
            return self._compile_results()
            
        except Exception as e:
            print(f"\n❌ Error during backtest: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _print_header(self):
        """Print execution header."""
        print("=" * 80)
        print("INTEGRATED BACKTEST EXECUTION")
        print("=" * 80)
        print(f"Timestamp: {self.timestamp}")
        print(f"Capital: R{self.initial_capital}")
        print(f"Data: {self.data_limit} candles")
        print(f"Slippage: {self.slippage*100:.1f}%, Fees: {self.fee_rate*100:.3f}%")
        print("-" * 80)
    
    def _display_summary(self):
        """Display summary of results."""
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        # Performance summary
        print(f"\n📊 PERFORMANCE")
        print(f"   Return:        {self.result.total_return_pct:+.2f}% (R{self.result.total_return:+.2f})")
        print(f"   Win Rate:      {self.result.win_rate:.1%}")
        print(f"   Trades:        {self.result.total_trades}")
        print(f"   Profit Factor: {self.result.profit_factor:.2f}")
        print(f"   Sharpe Ratio:  {self.result.sharpe_ratio:.2f}")
        
        # Risk summary
        print(f"\n⚠️  RISK")
        print(f"   Max Drawdown:  {self.result.max_drawdown:.2f}%")
        print(f"   Avg Win:       R{self.result.avg_win:.2f}")
        print(f"   Avg Loss:      R{self.result.avg_loss:.2f}")
        print(f"   Win/Loss:      {self.result.win_loss_ratio:.2f}")
        
        # Advanced metrics
        if hasattr(self.result, 'advanced_metrics'):
            adv = self.result.advanced_metrics
            print(f"\n⚡ ADVANCED METRICS")
            print(f"   Calmar Ratio:  {adv.get('calmar_ratio', 0):.2f}")
            print(f"   Sortino Ratio: {adv.get('sortino_ratio', 0):.2f}")
            print(f"   Risk of Ruin:  {adv.get('risk_of_ruin', 0):.1%}")
        
        # Regime performance
        if self.regime_stats and self.regime_stats['by_entry_regime']:
            print(f"\n🎭 REGIME PERFORMANCE")
            for regime, stats in self.regime_stats['by_entry_regime'].items():
                if stats['trades'] > 0:
                    print(f"   {regime.upper():10s}: {stats['trades']:2d} trades, "
                          f"Win: {stats.get('win_rate', 0):.1%}, "
                          f"Avg: R{stats.get('avg_pnl', 0):+.2f}")
    
    def _save_detailed_results(self):
        """Save detailed results to files."""
        # Save equity data
        equity_df = self.equity_curve.to_dataframe()
        equity_file = os.path.join(self.results_dir, "equity.csv")
        equity_df.to_csv(equity_file, index=False)
        
        # Save trades data
        trades_data = [t.to_dict() for t in self.result.trades]
        trades_file = os.path.join(self.results_dir, "trades.csv")
        import pandas as pd
        pd.DataFrame(trades_data).to_csv(trades_file, index=False)
        
        # Save metrics
        metrics = {
            'basic': {
                'total_return_pct': self.result.total_return_pct,
                'win_rate': self.result.win_rate,
                'profit_factor': self.result.profit_factor,
                'max_drawdown': self.result.max_drawdown,
                'sharpe_ratio': self.result.sharpe_ratio,
                'expectancy': self.result.expectancy,
                'total_trades': self.result.total_trades,
            },
            'advanced': getattr(self.result, 'advanced_metrics', {}),
            'regime': self.regime_stats,
            'parameters': {
                'initial_capital': self.initial_capital,
                'data_limit': self.data_limit,
                'slippage': self.slippage,
                'fee_rate': self.fee_rate,
                'timestamp': self.timestamp,
            }
        }
        
        metrics_file = os.path.join(self.results_dir, "metrics.json")
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
    
    def _compile_results(self) -> dict:
        """Compile all results into a dictionary."""
        has_result = self.result is not None
    
        return {
        'success': has_result,
        'timestamp': self.timestamp,
        'results_dir': self.results_dir,
        'report_file': self.report_file,
        'metrics': {
            'total_return_pct': getattr(self.result, 'total_return_pct', 0),
            'win_rate': getattr(self.result, 'win_rate', 0),
            'profit_factor': getattr(self.result, 'profit_factor', 0),
            'max_drawdown': getattr(self.result, 'max_drawdown', 0),
            'total_trades': getattr(self.result, 'total_trades', 0),
        }, # Removed the "if self.result else {}" here
        'files': {
            'html_report': self.report_file,
            'equity_csv': os.path.join(self.results_dir, "equity.csv") if has_result else None,
            'trades_csv': os.path.join(self.results_dir, "trades.csv") if has_result else None,
            'metrics_json': os.path.join(self.results_dir, "metrics.json") if has_result else None,
        }
    }
    
    def open_report(self):
        """Open HTML report in browser."""
        if self.report_file and os.path.exists(self.report_file):
            try:
                webbrowser.open(f'file://{os.path.abspath(self.report_file)}')
                print(f"✅ Report opened in browser: {self.report_file}")
            except Exception as e:
                print(f"⚠️  Could not open browser: {e}")
                print(f"📄 Report saved to: {self.report_file}")
        else:
            print("⚠️  No report file found.")


def run_sample_backtest():
    """Run a sample backtest for demonstration."""
    print("=" * 80)
    print("SAMPLE BACKTEST EXECUTION")
    print("=" * 80)
    
    # Create and run integrated backtest
    backtest = IntegratedBacktest(
        initial_capital=500,
        data_limit=1000,  # Reasonable amount
        slippage=0.001,
        fee_rate=0.00075
    )
    
    results = backtest.run(verbose=True)
    
    if results and results['success']:
        print(f"\n📊 Backtest completed successfully!")
        print(f"📁 Results directory: {results['results_dir']}")
        
        # Offer to open report
        response = input("\nOpen HTML report in browser? (y/n): ").lower()
        if response in ['y', 'yes']:
            backtest.open_report()
    else:
        print("\n❌ Backtest failed or no trades executed.")
    
    return results


def run_parameter_sweep():
    """Run multiple backtests with different parameters."""
    print("=" * 80)
    print("PARAMETER SWEEP ANALYSIS")
    print("=" * 80)
    
    # Define parameters to test
    capital_values = [500, 1000, 2000]
    data_limits = [500, 1000, 2000]
    
    results = []
    
    for capital in capital_values:
        for data_limit in data_limits:
            print(f"\n▶️  Testing: Capital=R{capital}, Data={data_limit} candles")
            
            backtest = IntegratedBacktest(
                initial_capital=capital,
                data_limit=data_limit,
                slippage=0.001,
                fee_rate=0.00075
            )
            
            result = backtest.run(verbose=False)
            
            if result and result['success']:
                results.append({
                    'capital': capital,
                    'data_limit': data_limit,
                    'return_pct': result['metrics']['total_return_pct'],
                    'win_rate': result['metrics']['win_rate'],
                    'trades': result['metrics']['total_trades'],
                })
                
                print(f"   Return: {result['metrics']['total_return_pct']:+.2f}%, "
                      f"Win: {result['metrics']['win_rate']:.1%}, "
                      f"Trades: {result['metrics']['total_trades']}")
            else:
                print(f"   No trades executed")
    
    # Display summary
    if results:
        print("\n" + "=" * 80)
        print("PARAMETER SWEEP SUMMARY")
        print("=" * 80)
        
        # Sort by return
        results.sort(key=lambda x: x['return_pct'], reverse=True)
        
        print("\n🏆 Best Parameters:")
        for i, r in enumerate(results[:3], 1):
            print(f"   {i}. R{r['capital']} with {r['data_limit']} candles: "
                  f"{r['return_pct']:+.2f}% return, {r['win_rate']:.1%} win rate")
        
        # Save results
        sweep_dir = "parameter_sweeps"
        os.makedirs(sweep_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sweep_file = os.path.join(sweep_dir, f"sweep_{timestamp}.json")
        
        with open(sweep_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📊 Results saved to: {sweep_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run integrated backtest")
    parser.add_argument("--mode", choices=["single", "sweep"], default="single",
                       help="Backtest mode: single test or parameter sweep")
    
    args = parser.parse_args()
    
    if args.mode == "single":
        run_sample_backtest()
    elif args.mode == "sweep":
        run_parameter_sweep()
# tests/test_integrated_system.py
"""
Test the fully integrated backtest system.
"""

import pytest
import os
import json
from datetime import datetime
from scripts.run_integrated_backtest import IntegratedBacktest


class TestIntegratedSystem:
    """Test the fully integrated backtest system."""
    
    def test_integrated_backtest_creation(self):
        """Test that integrated backtest can be created."""
        backtest = IntegratedBacktest(
            initial_capital=500,
            data_limit=100,
            slippage=0.001,
            fee_rate=0.00075
        )
        
        assert backtest.initial_capital == 500
        assert backtest.data_limit == 100
        assert backtest.timestamp is not None
        assert os.path.exists(backtest.results_dir)
    
    @pytest.mark.skipif(
        True,  # Skip by default as it requires data
        reason="Requires database with sufficient historical data"
    )
    def test_integrated_backtest_execution(self, tmp_path):
        """Test complete integrated backtest execution."""
        # Use temporary directory for results
        import tempfile
        temp_dir = tempfile.mkdtemp()
        
        # Create backtest with minimal data
        backtest = IntegratedBacktest(
            initial_capital=500,
            data_limit=200,  # Small dataset
            slippage=0.001,
            fee_rate=0.00075
        )
        
        # Override results directory
        backtest.results_dir = os.path.join(temp_dir, "test_results")
        os.makedirs(backtest.results_dir, exist_ok=True)
        
        # Run backtest
        results = backtest.run(verbose=False)
        
        # Check results structure
        assert results is not None
        assert 'success' in results
        assert 'timestamp' in results
        assert 'results_dir' in results
        
        # Check files were created
        if results['success']:
            assert os.path.exists(results['results_dir'])
            assert 'report_file' in results
            assert results['report_file'] is not None
    
    def test_results_compilation(self):
        """Test results compilation method."""
        backtest = IntegratedBacktest(initial_capital=500)
        
        # Mock result object
        class MockResult:
            total_return_pct = 10.5
            win_rate = 0.6
            profit_factor = 1.8
            max_drawdown = 15.2
            total_trades = 25
        
        backtest.result = MockResult()
        backtest.report_file = "/fake/path/report.html"
        
        results = backtest._compile_results()
        
        assert results['success'] == True
        assert results['metrics']['total_return_pct'] == 10.5
        assert results['metrics']['win_rate'] == 0.6
        assert results['files']['html_report'] == "/fake/path/report.html"
    
    def test_empty_results(self):
        """Test compilation with no results."""
        backtest = IntegratedBacktest(initial_capital=500)
        
        results = backtest._compile_results()
        
        assert results['success'] == False
        assert results['metrics']['total_return_pct'] == 0
        assert results['report_file'] is None


def test_backtest_reporter_creation():
    """Test that backtest reporter can be created."""
    try:
        from backtest.reporting import BacktestReporter
        
        reporter = BacktestReporter(output_dir="test_reports")
        
        assert reporter.output_dir == "test_reports"
        assert hasattr(reporter, 'generate_report')
        assert hasattr(reporter, 'open_report')
        
        # Cleanup
        import shutil
        if os.path.exists("test_reports"):
            shutil.rmtree("test_reports")
            
    except ImportError as e:
        pytest.skip(f"BacktestReporter not available: {e}")


def test_html_generation():
    """Test HTML report generation."""
    try:
        from backtest.reporting import BacktestReporter
        
        reporter = BacktestReporter(output_dir="test_html")
        
        # Create mock data
        class MockResult:
            trades = []
            total_return_pct = 5.2
            total_return = 26.0
            win_rate = 0.6
            profit_factor = 1.8
            max_drawdown = 12.5
            total_trades = 5
            sharpe_ratio = 0.85
            expectancy = 3.2
            avg_win = 8.0
            avg_loss = -5.5
            win_loss_ratio = 1.45
            largest_win = 12.0
            largest_loss = -7.5
            advanced_metrics = {
                'calmar_ratio': 0.42,
                'sortino_ratio': 0.92,
                'ulcer_index': 0.032,
                'risk_of_ruin': 0.08,
                'kelly_criterion': 0.15,
                'recovery_factor': 2.08,
            }
        
        class MockEquityCurve:
            def get_equity_series(self):
                import pandas as pd
                return pd.Series([500, 510, 495, 520, 526])
            
            def get_statistics(self):
                return {
                    'peak_capital': 526.0,
                    'current_drawdown_pct': 0.0,
                    'max_drawdown_pct': 2.94,
                    'volatility_pct': 2.1,
                    'winning_periods': 3,
                    'losing_periods': 1,
                }
            
            def to_dataframe(self):
                import pandas as pd
                return pd.DataFrame({
                    'capital': [500, 510, 495, 520, 526],
                    'timestamp': pd.date_range('2024-01-01', periods=5)
                })
        
        result = MockResult()
        equity_curve = MockEquityCurve()
        regime_stats = {'by_entry_regime': {}}
        
        # Generate report
        html_file = reporter.generate_report(result, equity_curve, regime_stats)
        
        assert html_file is not None
        assert os.path.exists(html_file)
        assert html_file.endswith('.html')
        
        # Check HTML content
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert '<html' in content
            assert 'Backtest Report' in content
            assert 'Total Return' in content
        
        # Cleanup
        import shutil
        if os.path.exists("test_html"):
            shutil.rmtree("test_html")
            
    except ImportError as e:
        pytest.skip(f"BacktestReporter not available: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("INTEGRATED SYSTEM TESTS")
    print("=" * 60)
    
    pytest.main([__file__, '-v'])
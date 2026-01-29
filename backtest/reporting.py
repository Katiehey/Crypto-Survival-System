# backtest/reporting.py
"""
Comprehensive reporting system for backtest results.
Generates HTML reports, integrates visualizations, and provides analysis.
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any
import webbrowser
from pathlib import Path

try:
    from backtest.visualization import BacktestVisualizer
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False


class BacktestReporter:
    """
    Generate comprehensive backtest reports.
    
    Creates:
    - HTML report with interactive elements
    - Summary statistics
    - Performance metrics
    - Visualizations
    - Recommendations
    """
    
    def __init__(self, output_dir: str = "backtest_reports"):
        """
        Initialize reporter.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Template for HTML report
        self.html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                {styles}
            </style>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        </head>
        <body>
            <div class="container">
                {header}
                {summary}
                {metrics}
                {charts}
                {trades}
                {recommendations}
                {footer}
            </div>
            <script>
                {scripts}
            </script>
        </body>
        </html>
        """
        
        self.styles = """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            border-radius: 10px;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .section {
            padding: 30px;
            border-bottom: 1px solid #eee;
        }
        
        .section:last-child {
            border-bottom: none;
        }
        
        .section-title {
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .metric-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            transition: transform 0.3s;
            border: 1px solid #e9ecef;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        
        .metric-label {
            color: #6c757d;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .positive {
            color: #28a745 !important;
        }
        
        .negative {
            color: #dc3545 !important;
        }
        
        .neutral {
            color: #ffc107 !important;
        }
        
        .chart-container {
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        
        .trades-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        .trades-table th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
        }
        
        .trades-table td {
            padding: 12px;
            border-bottom: 1px solid #eee;
        }
        
        .trades-table tr:hover {
            background: #f8f9fa;
        }
        
        .recommendation {
            padding: 15px;
            margin: 10px 0;
            border-radius: 6px;
            border-left: 4px solid;
        }
        
        .recommendation.good {
            background: #d4edda;
            border-left-color: #28a745;
        }
        
        .recommendation.warning {
            background: #fff3cd;
            border-left-color: #ffc107;
        }
        
        .recommendation.bad {
            background: #f8d7da;
            border-left-color: #dc3545;
        }
        
        .footer {
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 0.9em;
            border-top: 1px solid #eee;
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 10px;
                border-radius: 0;
            }
            
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            
            .section {
                padding: 20px;
            }
        }
        """
        
        self.scripts = """
        // Simple script for interactive elements
        document.addEventListener('DOMContentLoaded', function() {
            // Add click handlers to metric cards
            document.querySelectorAll('.metric-card').forEach(card => {
                card.addEventListener('click', function() {
                    const value = this.querySelector('.metric-value').textContent;
                    const label = this.querySelector('.metric-label').textContent;
                    alert(label + ': ' + value);
                });
            });
            
            // Toggle trade details
            document.querySelectorAll('.trade-detail').forEach(detail => {
                detail.style.display = 'none';
            });
            
            document.querySelectorAll('.trades-table tr').forEach(row => {
                row.addEventListener('click', function() {
                    const detail = this.nextElementSibling;
                    if (detail && detail.classList.contains('trade-detail')) {
                        detail.style.display = detail.style.display === 'none' ? 'table-row' : 'none';
                    }
                });
            });
        });
        """
    
    def generate_report(
        self,
        backtest_result,
        equity_curve,
        regime_stats: Dict,
        timestamp: str = None
    ) -> str:
        """
        Generate complete HTML report.
        
        Args:
            backtest_result: BacktestResult object
            equity_curve: EquityCurve object
            regime_stats: Regime analysis statistics
            timestamp: Report timestamp
            
        Returns:
            Path to generated HTML file
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create report directory
        report_dir = os.path.join(self.output_dir, timestamp)
        os.makedirs(report_dir, exist_ok=True)
        
        # Generate visualizations if available
        chart_files = {}
        if VISUALIZATION_AVAILABLE:
            visualizer = BacktestVisualizer(output_dir=report_dir)
            
            # Generate plots
            equity_series = equity_curve.get_equity_series()
            visualizer.plot_all(equity_series, backtest_result.trades, "")
            
            # Store chart file paths
            chart_files = {
                'equity_curve': os.path.join(report_dir, "equity_curve.png"),
                'returns_distribution': os.path.join(report_dir, "returns_distribution.png"),
                'monthly_returns': os.path.join(report_dir, "monthly_returns.png"),
                'trade_analysis': os.path.join(report_dir, "trade_analysis.png"),
            }
        
        # Generate HTML content
        html_content = self._generate_html_content(
            backtest_result, equity_curve, regime_stats, chart_files, timestamp
        )
        
        # Save HTML file
        html_file = os.path.join(report_dir, "backtest_report.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Save data files
        self._save_data_files(backtest_result, equity_curve, report_dir)
        
        return html_file
    
    def _generate_html_content(
        self,
        backtest_result,
        equity_curve,
        regime_stats: Dict,
        chart_files: Dict,
        timestamp: str
    ) -> str:
        """Generate HTML content for report."""
        
        # Header
        header = f"""
        <div class="header">
            <h1>📊 Backtest Report</h1>
            <div class="subtitle">
                Strategy: SimpleTrendStrategy | Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
        """
        
        # Summary section
        summary = self._generate_summary_section(backtest_result, equity_curve)
        
        # Metrics section
        metrics = self._generate_metrics_section(backtest_result)
        
        # Charts section
        charts = self._generate_charts_section(chart_files)
        
        # Trades section
        trades = self._generate_trades_section(backtest_result)
        
        # Recommendations section
        recommendations = self._generate_recommendations_section(backtest_result)
        
        # Footer
        footer = f"""
        <div class="footer">
            <p>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Backtest Framework v1.0 | Crypto Survival System</p>
        </div>
        """
        
        # Assemble HTML
        html = self.html_template.format(
            title=f"Backtest Report - {timestamp}",
            styles=self.styles,
            scripts=self.scripts,
            header=header,
            summary=summary,
            metrics=metrics,
            charts=charts,
            trades=trades,
            recommendations=recommendations,
            footer=footer
        )
        
        return html
    
    def _generate_summary_section(self, backtest_result, equity_curve) -> str:
        """Generate summary section HTML."""
        equity_stats = equity_curve.get_statistics()
        
        summary_html = f"""
        <div class="section">
            <h2 class="section-title">📈 Executive Summary</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Total Return</div>
                    <div class="metric-value {self._get_color_class(backtest_result.total_return_pct, 0)}">
                        {backtest_result.total_return_pct:+.2f}%
                    </div>
                    <div>R{backtest_result.total_return:+.2f}</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-value {self._get_color_class(backtest_result.win_rate * 100, 50)}">
                        {backtest_result.win_rate:.1%}
                    </div>
                    <div>{backtest_result.total_trades} trades</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">Profit Factor</div>
                    <div class="metric-value {self._get_color_class(backtest_result.profit_factor, 1.5)}">
                        {backtest_result.profit_factor:.2f}
                    </div>
                    <div>Wins/Losses</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">Max Drawdown</div>
                    <div class="metric-value {self._get_color_class(-backtest_result.max_drawdown, -15)}">
                        {backtest_result.max_drawdown:.2f}%
                    </div>
                    <div>Peak: R{equity_stats['peak_capital']:.2f}</div>
                </div>
            </div>
        </div>
        """
        
        return summary_html
    
    def _generate_metrics_section(self, backtest_result) -> str:
        """Generate metrics section HTML."""
        
        # Basic metrics
        basic_metrics = [
            ("Sharpe Ratio", backtest_result.sharpe_ratio, 0.5),
            ("Expectancy", backtest_result.expectancy, 0),
            ("Avg Win", backtest_result.avg_win, 0),
            ("Avg Loss", backtest_result.avg_loss, 0),
            ("Win/Loss Ratio", backtest_result.win_loss_ratio, 1.0),
            ("Largest Win", backtest_result.largest_win, 0),
            ("Largest Loss", backtest_result.largest_loss, 0),
        ]
        
        # Advanced metrics
        advanced_metrics = []
        if hasattr(backtest_result, 'advanced_metrics'):
            adv = backtest_result.advanced_metrics
            advanced_metrics = [
                ("Calmar Ratio", adv.get('calmar_ratio', 0), 1.0),
                ("Sortino Ratio", adv.get('sortino_ratio', 0), 0.5),
                ("Ulcer Index", adv.get('ulcer_index', 0), 0.05),
                ("Risk of Ruin", adv.get('risk_of_ruin', 0), 0.1),
                ("Kelly %", adv.get('kelly_criterion', 0) * 100, 10),
                ("Recovery Factor", adv.get('recovery_factor', 0), 1.0),
            ]
        
        # Generate metric cards
        metric_cards = ""
        for label, value, threshold in basic_metrics + advanced_metrics:
            if isinstance(value, float):
                if label in ["Avg Win", "Avg Loss", "Largest Win", "Largest Loss"]:
                    display_value = f"R{value:.2f}"
                elif label == "Risk of Ruin":
                    display_value = f"{value:.1%}"
                elif label == "Kelly %":
                    display_value = f"{value:.1f}%"
                elif abs(value) > 1000:  # Very large numbers
                    display_value = f"{value:.2e}"
                else:
                    display_value = f"{value:.2f}"
            else:
                display_value = str(value)
            
            metric_cards += f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value {self._get_color_class(value, threshold, label)}">
                    {display_value}
                </div>
            </div>
            """
        
        metrics_html = f"""
        <div class="section">
            <h2 class="section-title">📊 Performance Metrics</h2>
            <div class="metrics-grid">
                {metric_cards}
            </div>
        </div>
        """
        
        return metrics_html
    
    def _generate_charts_section(self, chart_files: Dict) -> str:
        """Generate charts section HTML."""
        if not chart_files:
            return """
            <div class="section">
                <h2 class="section-title">📈 Charts</h2>
                <p>Visualizations require matplotlib. Install with: <code>pip install matplotlib</code></p>
            </div>
            """
        
        charts_html = """
        <div class="section">
            <h2 class="section-title">📈 Charts & Visualizations</h2>
        """
        
        for chart_name, chart_file in chart_files.items():
            if os.path.exists(chart_file):
                chart_title = chart_name.replace('_', ' ').title()
                charts_html += f"""
                <div class="chart-container">
                    <h3>{chart_title}</h3>
                    <img src="{os.path.basename(chart_file)}" alt="{chart_title}" style="width:100%; max-width:800px;">
                </div>
                """
        
        charts_html += "</div>"
        return charts_html
    
    def _generate_trades_section(self, backtest_result) -> str:
        """Generate trades section HTML."""
        if not backtest_result.trades:
            return """
            <div class="section">
                <h2 class="section-title">💼 Trades</h2>
                <p>No trades executed during backtest period.</p>
            </div>
            """
        
        # Limit to first 20 trades for readability
        display_trades = backtest_result.trades[:20]
        
        # Generate trade rows
        trade_rows = ""
        for i, trade in enumerate(display_trades):
            pnl_class = "positive" if trade.pnl > 0 else "negative"
            trade_rows += f"""
            <tr>
                <td>{i+1}</td>
                <td>{trade.entry_time.strftime('%Y-%m-%d %H:%M')}</td>
                <td>{trade.exit_time.strftime('%Y-%m-%d %H:%M')}</td>
                <td>R{trade.size:.2f}</td>
                <td class="{pnl_class}">R{trade.pnl:+.2f}</td>
                <td>{trade.pnl_percent:+.2f}%</td>
                <td>{trade.entry_regime} → {trade.exit_regime}</td>
                <td>{trade.exit_reason}</td>
            </tr>
            <tr class="trade-detail">
                <td colspan="8">
                    <strong>Details:</strong> {trade.trade_id} | Duration: {trade.duration:.1f}h | 
                    Entry: ${trade.entry_price:.2f} | Exit: R{trade.exit_price:.2f}
                </td>
            </tr>
            """
        
        trades_html = f"""
        <div class="section">
            <h2 class="section-title">💼 Trades ({len(backtest_result.trades)} total)</h2>
            <p>Showing first {len(display_trades)} trades. Click any row for details.</p>
            <table class="trades-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Entry Time</th>
                        <th>Exit Time</th>
                        <th>Size</th>
                        <th>PnL</th>
                        <th>%</th>
                        <th>Regime</th>
                        <th>Exit Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {trade_rows}
                </tbody>
            </table>
            {f'<p style="margin-top: 15px;"><em>... and {len(backtest_result.trades) - len(display_trades)} more trades</em></p>' if len(backtest_result.trades) > len(display_trades) else ''}
        </div>
        """
        
        return trades_html
    
    def _generate_recommendations_section(self, backtest_result) -> str:
        """Generate recommendations section HTML."""
        recommendations = []
        
        # Evaluate performance
        if backtest_result.total_return_pct > 15:
            recommendations.append((
                "Excellent returns achieved",
                "Strategy shows strong profitability. Consider proceeding to paper trading with micro-capital.",
                "good"
            ))
        elif backtest_result.total_return_pct > 5:
            recommendations.append((
                "Positive returns achieved",
                "Strategy is profitable but could benefit from optimization.",
                "good"
            ))
        elif backtest_result.total_return_pct > 0:
            recommendations.append((
                "Marginal returns",
                "Strategy barely breaks even. Needs parameter optimization.",
                "warning"
            ))
        else:
            recommendations.append((
                "Negative returns",
                "Strategy is losing money. Review logic and parameters.",
                "bad"
            ))
        
        # Win rate evaluation
        if backtest_result.win_rate > 0.6:
            recommendations.append((
                "High win rate",
                "Excellent consistency in trade outcomes.",
                "good"
            ))
        elif backtest_result.win_rate > 0.5:
            recommendations.append((
                "Good win rate",
                "More winning trades than losing trades.",
                "good"
            ))
        elif backtest_result.win_rate > 0.4:
            recommendations.append((
                "Moderate win rate",
                "Win rate needs improvement. Focus on entry timing.",
                "warning"
            ))
        else:
            recommendations.append((
                "Low win rate",
                "Too many losing trades. Review entry signals.",
                "bad"
            ))
        
        # Profit factor evaluation
        if backtest_result.profit_factor > 2.0:
            recommendations.append((
                "Outstanding profit factor",
                "Winners significantly outweigh losers.",
                "good"
            ))
        elif backtest_result.profit_factor > 1.5:
            recommendations.append((
                "Good profit factor",
                "Healthy ratio of winning to losing trades.",
                "good"
            ))
        elif backtest_result.profit_factor > 1.0:
            recommendations.append((
                "Marginal profit factor",
                "Barely profitable. Risk management is critical.",
                "warning"
            ))
        else:
            recommendations.append((
                "Poor profit factor",
                "Losing money on average. Strategy needs revision.",
                "bad"
            ))
        
        # Drawdown evaluation
        if backtest_result.max_drawdown < 10:
            recommendations.append((
                "Low drawdown",
                "Excellent risk management. Capital preservation is strong.",
                "good"
            ))
        elif backtest_result.max_drawdown < 20:
            recommendations.append((
                "Moderate drawdown",
                "Acceptable risk levels. Consider tighter stops.",
                "warning"
            ))
        else:
            recommendations.append((
                "High drawdown",
                "Excessive risk. Reduce position sizes or tighten stops.",
                "bad"
            ))
        
        # Generate HTML
        rec_html = ""
        for title, description, style in recommendations:
            rec_html += f"""
            <div class="recommendation {style}">
                <strong>{title}</strong>
                <p>{description}</p>
            </div>
            """
        
        recommendations_html = f"""
        <div class="section">
            <h2 class="section-title">🎯 Recommendations</h2>
            {rec_html}
            <div style="margin-top: 20px;">
                <h3>Next Steps:</h3>
                <ol style="margin-left: 20px;">
                    <li>Review the metrics and visualizations above</li>
                    <li>Analyze trade-by-trade performance</li>
                    <li>Optimize strategy parameters if needed</li>
                    <li>Run multiple backtests for robustness</li>
                    <li>Proceed to paper trading if results are positive</li>
                </ol>
            </div>
        </div>
        """
        
        return recommendations_html
    
    def _get_color_class(self, value: float, threshold: float, label: str = "") -> str:
        """
        Determine CSS class based on value and threshold.
        
        Args:
            value: The value to evaluate
            threshold: Threshold for evaluation
            label: Metric label for special cases
            
        Returns:
            CSS class name
        """
        if label == "Risk of Ruin":
            # Lower is better for risk of ruin
            return "positive" if value < threshold else ("warning" if value < threshold * 2 else "negative")
        elif label == "Ulcer Index":
            # Lower is better for ulcer index
            return "positive" if value < threshold else ("warning" if value < threshold * 2 else "negative")
        elif label == "Avg Loss":
            # Less negative is better
            return "positive" if value > threshold else ("warning" if value > threshold * 0.5 else "negative")
        elif "Loss" in label:
            # Less negative is better for loss metrics
            return "positive" if value > threshold else ("warning" if value > threshold * 0.5 else "negative")
        else:
            # Higher is better for most metrics
            if value >= threshold * 1.5:
                return "positive"
            elif value >= threshold:
                return "warning"
            else:
                return "negative"
    
    def _save_data_files(self, backtest_result, equity_curve, report_dir: str):
        """Save data files for analysis."""
        # Save equity data
        equity_df = equity_curve.to_dataframe()
        equity_file = os.path.join(report_dir, "equity_data.csv")
        equity_df.to_csv(equity_file, index=False)
        
        # Save trades data
        trades_data = []
        for trade in backtest_result.trades:
            trades_data.append(trade.to_dict())
        
        trades_file = os.path.join(report_dir, "trades_data.csv")
        pd.DataFrame(trades_data).to_csv(trades_file, index=False)
        
        # Save summary JSON
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_return_pct': backtest_result.total_return_pct,
            'win_rate': backtest_result.win_rate,
            'profit_factor': backtest_result.profit_factor,
            'max_drawdown': backtest_result.max_drawdown,
            'total_trades': backtest_result.total_trades,
            'sharpe_ratio': backtest_result.sharpe_ratio,
        }
        
        summary_file = os.path.join(report_dir, "summary.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
    
    def open_report(self, html_file: str):
        """
        Open HTML report in default browser.
        
        Args:
            html_file: Path to HTML file
        """
        try:
            webbrowser.open(f'file://{os.path.abspath(html_file)}')
            print(f"✅ Report opened in browser: {html_file}")
        except Exception as e:
            print(f"⚠️  Could not open browser: {e}")
            print(f"📄 Report saved to: {html_file}")


def main():
    """Test reporter with sample data."""
    print("=" * 60)
    print("BACKTEST REPORTER TEST")
    print("=" * 60)
    
    # Create sample data
    from backtest.trade import create_trade
    from backtest.equity_curve import EquityCurve, create_equity_curve_from_trades
    from datetime import datetime
    
    # Create sample trades
    trades = [
        create_trade("W1", datetime(2024, 1, 1), 42000, 'trend',
                    datetime(2024, 1, 2), 42500, 'trend', 'exit', 250),
        create_trade("L1", datetime(2024, 1, 3), 42500, 'trend',
                    datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250),
        create_trade("W2", datetime(2024, 1, 5), 41500, 'range',
                    datetime(2024, 1, 6), 42000, 'trend', 'exit', 250),
        create_trade("W3", datetime(2024, 1, 8), 42000, 'trend',
                    datetime(2024, 1, 9), 42400, 'trend', 'exit', 250),
        create_trade("L2", datetime(2024, 1, 10), 42400, 'trend',
                    datetime(2024, 1, 10), 41580, 'chaos', 'stop_loss', 250),
    ]
    
    # Create equity curve
    equity_curve = create_equity_curve_from_trades(trades, 500)
    
    # Create mock backtest result
    class MockResult:
        def __init__(self, trades, equity_curve):
            self.trades = trades
            self.total_return_pct = 5.2
            self.total_return = 26.0
            self.win_rate = 0.6
            self.profit_factor = 1.8
            self.max_drawdown = 12.5
            self.total_trades = len(trades)
            self.sharpe_ratio = 0.85
            self.expectancy = 3.2
            self.avg_win = 8.0
            self.avg_loss = -5.5
            self.win_loss_ratio = 1.45
            self.largest_win = 12.0
            self.largest_loss = -7.5
            self.advanced_metrics = {
                'calmar_ratio': 0.42,
                'sortino_ratio': 0.92,
                'ulcer_index': 0.032,
                'risk_of_ruin': 0.08,
                'kelly_criterion': 0.15,
                'recovery_factor': 2.08,
            }
    
    result = MockResult(trades, equity_curve)
    
    # Create regime stats
    regime_stats = {
        'by_entry_regime': {
            'trend': {'trades': 3, 'avg_pnl': 4.2},
            'range': {'trades': 2, 'avg_pnl': 6.8},
        }
    }
    
    # Generate report
    reporter = BacktestReporter(output_dir="test_reports")
    html_file = reporter.generate_report(result, equity_curve, regime_stats)
    
    print(f"\n✅ Report generated: {html_file}")
    
    # Try to open in browser
    reporter.open_report(html_file)
    
    print("\n" + "=" * 60)
    print("✅ Reporter test complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
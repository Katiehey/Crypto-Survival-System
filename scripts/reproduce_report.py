import os
import glob
import json
import pandas as pd
from datetime import datetime, timedelta
from backtest.reporting import BacktestReporter

class MockEquityCurve:
    def __init__(self, df):
        # Fix: Ensure there is a DatetimeIndex for resampling
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            # Create a fake hourly timeline if no timestamp exists
            start_date = datetime.now() - timedelta(hours=len(df))
            df['timestamp'] = [start_date + timedelta(hours=i) for i in range(len(df))]
        
        self.df = df.set_index('timestamp')

    def get_equity_series(self):
        col = 'capital' if 'capital' in self.df.columns else self.df.columns[0]
        return self.df[col]
    
    def to_dataframe(self):
        return self.df.reset_index()
    
    def get_statistics(self):
        col = 'capital' if 'capital' in self.df.columns else self.df.columns[0]
        return {"peak_capital": self.df[col].max() if not self.df.empty else 0}

class MockResult:
    def __init__(self, data):
        meta = data.get('metadata', {})
        basic = data.get('basic_metrics', {})
        risk = data.get('risk_metrics', {})
        
        # 2. Executive Summary Metrics
        self.total_return_pct = basic.get('total_return_pct', 0.0)
        self.total_return = basic.get('total_return', 0.0)
        self.win_rate = basic.get('win_rate', 0.0)
        self.profit_factor = basic.get('profit_factor', 0.0)
        self.total_trades = basic.get('total_trades', 0)
        self.expectancy = basic.get('expectancy', 0.0)
        self.sharpe_ratio = basic.get('sharpe_ratio', 0.0)
        self.max_drawdown = risk.get('max_drawdown', 0.0)
        self.avg_win = risk.get('avg_win', 0.0)
        self.avg_loss = risk.get('avg_loss', 0.0)
        self.win_loss_ratio = risk.get('win_loss_ratio', 1.15)
        self.largest_win = risk.get('largest_win', 0.0)
        self.largest_loss = risk.get('largest_loss', 0.0)
        self.initial_capital = meta.get('initial_capital', 500)
        self.final_capital = basic.get('final_capital', 390.28)

        # 3. THE FIX: Extract trades from the root of the JSON
        self.trades = []
        raw_trades = data.get('trades', []) # Ensure this matches your JSON key
        
        for t in raw_trades:
            # We use a SimpleNamespace or a custom class to allow dot notation
            from types import SimpleNamespace
            trade_obj = SimpleNamespace(
                entry_time=pd.to_datetime(t.get('entry_time')),
                exit_time=pd.to_datetime(t.get('exit_time')),
                size=float(t.get('size', 0.0)),
                pnl=float(t.get('pnl_val', 0.0)),
                pnl_percent=float(t.get('pnl_pct', 0.0)),
                entry_regime=str(t.get('regime', 'N/A')),
                exit_reason=str(t.get('exit_reason', 'N/A')),
                duration=float(t.get('duration', 0.0))
            )
            self.trades.append(trade_obj)

    # This ensures "if not result.trades" evaluates correctly
    def __len__(self):
        return len(self.trades)

        

def run_repro_report():
    search_pattern = os.path.join("backtest_results", "**/*_complete_results.json")
    all_metrics = glob.glob(search_pattern, recursive=True)
    
    if not all_metrics:
        print("❌ No metrics.json found.")
        return
    
    metrics_path = max(all_metrics, key=os.path.getmtime)
    latest_folder = os.path.dirname(metrics_path)
    
    print(f"📂 Found data in: {latest_folder}")

    try:
        with open(metrics_path, 'r') as f:
            metrics_data = json.load(f)
        
        result = MockResult(metrics_data)
        
        # Check if we actually have trades in the MockResult
        print(f"💎 Trades found in memory: {len(result.trades)}")

        # Create dummy equity curve for the chart section
        equity_curve = MockEquityCurve(pd.DataFrame({'capital': [result.initial_capital, result.final_capital]}))
        
        report_dir = os.path.join(latest_folder, "reproduction")
        os.makedirs(report_dir, exist_ok=True)
        reporter = BacktestReporter(output_dir=report_dir)
        
        # 1. Generate standard report
        html_file = reporter.generate_report(result, equity_curve, {})

        # 2. FORCE INJECT HTML TABLE
        with open(html_file, 'r') as f:
            content = f.read()

        # Build the table rows
        rows_html = ""
        for i, t in enumerate(result.trades):
            pnl = getattr(t, 'pnl', 0.0)
            pnl_pct = getattr(t, 'pnl_percent', 0.0)
            color = "#28a745" if pnl > 0 else "#dc3545"
            
            rows_html += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">{i+1}</td>
                <td style="padding: 10px;">{t.entry_time}</td>
                <td style="padding: 10px;">R{getattr(t, 'size', 0):.2f}</td>
                <td style="padding: 10px; color: {color}; font-weight: bold;">R{pnl:+.2f}</td>
                <td style="padding: 10px; color: {color};">{pnl_pct:+.2f}%</td>
                <td style="padding: 10px;">{getattr(t, 'entry_regime', 'N/A')}</td>
                <td style="padding: 10px;">{getattr(t, 'exit_reason', 'N/A')}</td>
            </tr>"""

        full_table_html = f"""
        <div class="section">
            <h2 class="section-title">💼 Trades ({len(result.trades)} total)</h2>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #667eea; color: white; text-align: left;">
                            <th style="padding: 12px;">#</th>
                            <th style="padding: 12px;">Entry Time</th>
                            <th style="padding: 12px;">Size</th>
                            <th style="padding: 12px;">PnL</th>
                            <th style="padding: 12px;">%</th>
                            <th style="padding: 12px;">Regime</th>
                            <th style="padding: 12px;">Exit Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
        """

        # Locate the Trades section and swap it
        import re
        # This regex looks for the div containing the "No trades executed" message
        pattern = r'<div class="section">\s*<h2 class="section-title">💼 Trades</h2>\s*<p>No trades executed during backtest period.</p>\s*</div>'
        new_content = re.sub(pattern, full_table_html, content)

        with open(html_file, 'w') as f:
            f.write(new_content)

        print(f"🚀 SUCCESS: Trade table forced into {html_file}")
        reporter.open_report(html_file)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_repro_report()
"""Run a longer backtest over the full local DB and export results.

Usage:
    PYTHONPATH=. python3 scripts/run_full_backtest.py
"""
from datetime import datetime
import os
import logging

logging.basicConfig(level=logging.INFO)

from paper_trading import PaperTradingSystem
from paper_trading.data_provider import HistoricalDataProvider
from risk.engine import RiskEngine
from strategies.simple_trend import SimpleTrendStrategy
from paper_trading.execution import ExecutionSimulator


def run_full_backtest(limit=1000000):
    # Ensure output dir
    out_dir = os.path.join('backtest_results')
    os.makedirs(out_dir, exist_ok=True)

    # Prepare provider and load as much as available
    provider = HistoricalDataProvider()
    df = provider.get_historical_data(limit=limit)

    class _StaticProvider:
        def get_historical_data(self, limit=1000, start_date=None, end_date=None):
            return df

        def get_latest_candle(self, *a, **k):
            return None

    # Setup system
    system = PaperTradingSystem(
        initial_capital=500,
        symbol="BTC/USDT",
        timeframe="1h",
        speed="instant",
        data_source="historical"
    )

    strategy = SimpleTrendStrategy()
    risk = RiskEngine(capital=system.initial_capital)
    exec_sim = ExecutionSimulator()

    system.setup(
        strategy=strategy,
        risk_engine=risk,
        data_provider=_StaticProvider(),
        execution_simulator=exec_sim
    )

    # Run the simulation
    logging.info(f"Running full backtest with limit={limit} (DB may provide fewer candles)")
    system.start()

    # Export results
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    trades_fp = os.path.join(out_dir, f"{ts}_trades.csv")
    equity_fp = os.path.join(out_dir, f"{ts}_equity.csv")

    try:
        import pandas as pd

        if system.closed_trades:
            trades_df = pd.DataFrame(system.closed_trades)
            trades_df.to_csv(trades_fp, index=False)
            logging.info(f"Wrote trades to {trades_fp}")
        else:
            logging.info("No closed trades to export")

        if system.equity_history:
            eq_df = pd.DataFrame(system.equity_history)
            eq_df.to_csv(equity_fp, index=False)
            logging.info(f"Wrote equity history to {equity_fp}")
        else:
            logging.info("No equity history to export")
    except Exception as e:
        logging.error(f"Failed to export CSVs: {e}")

    # Print summary to console
    system.print_summary()


if __name__ == '__main__':
    run_full_backtest()

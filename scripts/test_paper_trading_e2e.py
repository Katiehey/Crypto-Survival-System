"""End-to-end paper trading smoke test.

Creates the paper trading system with R500 starting capital, runs a short
historical replay (instant speed) and prints the performance summary.

Run:
    python scripts/test_paper_trading_e2e.py
"""
from datetime import datetime, timedelta
import logging

# Use INFO level for E2E smoke tests
logging.basicConfig(level=logging.INFO)

from paper_trading import PaperTradingSystem
from paper_trading.data_provider import HistoricalDataProvider
from risk.engine import RiskEngine
from strategies.simple_trend import SimpleTrendStrategy
from paper_trading.execution import ExecutionSimulator


def run_e2e(limit=200):
    # Prepare components
    provider = HistoricalDataProvider()
    df = provider.get_historical_data(limit=limit)

    # Lightweight wrapper provider that returns the prepared df
    class _StaticProvider:
        def get_historical_data(self, limit=1000, start_date=None, end_date=None):
            return df

        def get_latest_candle(self, *a, **k):
            return None

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

    # Wire system
    system.setup(
        strategy=strategy,
        risk_engine=risk,
        data_provider=_StaticProvider(),
        execution_simulator=exec_sim
    )

    # Run the historical simulation (no delays)
    system.start()

    # Print summary
    system.print_summary()


if __name__ == "__main__":
    print("Running E2E paper trading smoke test (R500)...")
    run_e2e(limit=200)

"""Dry-run paper trading runner.

Runs the `PaperTradingSystem` in a safe dry-run mode: executes through the
historical data pipeline, simulates executions, but does not submit any real
orders. Intended as a final smoke before enabling live paper trading.

Usage:
    PYTHONPATH=. python3 scripts/dry_run_paper_trading.py --limit 200 --speed instant
"""
import argparse
import logging
from paper_trading import PaperTradingSystem
from paper_trading.data_provider import HistoricalDataProvider
from strategies.simple_trend import SimpleTrendStrategy
from risk.engine import RiskEngine


class NoOpExecutionSimulator:
    """Execution simulator that mimics fills but only logs results (no external calls)."""

    def execute_order(self, symbol, side, size, price):
        class Exec:
            success = True
            filled_size = size
            execution_price = price
            fee = 0.0
            reason = 'dry_run'

        logging.info(f"[DryRunExec] {side} {symbol} size=R{size:.2f} @ {price:.2f}")
        return Exec()


def main(limit: int = 500, speed: str = 'instant'):
    logging.basicConfig(level=logging.INFO)

    system = PaperTradingSystem(
        initial_capital=500.0,
        symbol='BTC/USDT',
        timeframe='1h',
        speed=speed,
        data_source='historical'
    )

    # Components
    provider = HistoricalDataProvider(symbol='BTC/USDT', timeframe='1h')
    strategy = SimpleTrendStrategy()
    risk = RiskEngine(capital=system.initial_capital)
    exec_sim = NoOpExecutionSimulator()

    system.setup(strategy=strategy, risk_engine=risk, data_provider=provider, execution_simulator=exec_sim)

    # Run a shortened historical replay for dry-run
    provider.get_historical_data(limit=limit)  # warm-up pipeline
    system.is_running = True
    system._run_historical_simulation()

    system.print_summary()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=500)
    p.add_argument('--speed', type=str, default='instant')
    args = p.parse_args()
    main(limit=args.limit, speed=args.speed)

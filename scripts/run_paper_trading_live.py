"""Run a short, safe paper trading session (simulated or testnet).

Usage examples:
  # Simulated short run (recommended initially)
  python scripts/run_paper_trading_live.py --mode simulated --capital 500 --hours 2

  # Testnet (requires exchange config/test keys)
  python scripts/run_paper_trading_live.py --mode testnet --capital 500 --hours 2
"""
import argparse
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

from paper_trading import PaperTradingSystem
from paper_trading.data_provider import HistoricalDataProvider
from paper_trading.data_provider import BaseDataProvider
from risk.engine import RiskEngine
from strategies.simple_trend import SimpleTrendStrategy
from paper_trading.execution import ExecutionSimulator


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['simulated', 'testnet'], default='simulated')
    p.add_argument('--capital', type=float, default=500)
    p.add_argument('--timeframe', type=str, default='1h')
    p.add_argument('--hours', type=int, default=2)
    return p.parse_args()


class SimulatedProvider(BaseDataProvider):
    def __init__(self, symbol='BTC/USDT', timeframe='1h'):
        super().__init__(symbol, timeframe)
        self._hist = HistoricalDataProvider()

    def get_latest_candle(self):
        # Return most recent candle from historical DB (safe fallback)
        df = self._hist.get_historical_data(limit=1)
        if df is None or df.empty:
            return None
        row = df.iloc[-1]
        return row.to_dict()


def main():
    args = parse_args()

    system = PaperTradingSystem(
        initial_capital=args.capital,
        symbol='BTC/USDT',
        timeframe=args.timeframe,
        speed='instant',
        data_source='live' if args.mode == 'testnet' else 'historical'
    )

    strategy = SimpleTrendStrategy()
    risk = RiskEngine(capital=system.initial_capital)
    exec_sim = ExecutionSimulator()

    if args.mode == 'testnet':
        # Attempt to use live feed; if it fails, fallback to simulated provider
        try:
            from paper_trading.live_feed import LiveDataFeed
            provider = LiveDataFeed(symbol=system.symbol, timeframe=system.timeframe)
        except Exception:
            logging.warning('Live feed unavailable, falling back to simulated provider')
            provider = SimulatedProvider()
    else:
        provider = SimulatedProvider()

    system.setup(strategy=strategy, risk_engine=risk, data_provider=provider, execution_simulator=exec_sim)

    # Run for a short duration
    system.start()
    end_time = datetime.now() + timedelta(hours=args.hours)
    try:
        while datetime.now() < end_time and system.is_running:
            # In live mode, the system loop runs internally; we just wait
            pass
    except KeyboardInterrupt:
        logging.info('Interrupted by user')
    finally:
        system.stop()
        system.print_summary()


if __name__ == '__main__':
    main()

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
import sys
import pathlib
import os

# Ensure project root is on sys.path for local script execution
project_root = pathlib.Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

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
    p.add_argument('--confirm-live', action='store_true', help='Confirm testnet/live run (required for --mode testnet)')
    return p.parse_args()


# Use SimulatedDataProvider for simulated runs (generates realtime-like candles).
from paper_trading.data_provider import SimulatedDataProvider as SimulatedProvider


def main():
    args = parse_args()

    # Safety: require explicit confirmation to run in testnet mode
    if args.mode == 'testnet' and not args.confirm_live:
        raise SystemExit("Refusing to run in testnet mode without --confirm-live. Use --confirm-live to acknowledge risks.")

    # Basic secrets check for testnet mode
    if args.mode == 'testnet':
        missing = []
        if not os.getenv('BINANCE_API_KEY') or not os.getenv('BINANCE_API_SECRET'):
            missing.append('BINANCE API key/secret')
        if missing:
            raise SystemExit(f"Missing required credentials for testnet: {', '.join(missing)}. Set in environment or .env and retry.")

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
            # If exchange failed to initialize (e.g., bad API keys), fall back
            if getattr(provider, 'exchange', None) is None:
                logging.warning('Live feed exchange not initialized (bad keys or network). Falling back to simulated provider')
                provider = SimulatedProvider()
        except Exception:
            logging.warning('Live feed unavailable, falling back to simulated provider')
            provider = SimulatedProvider()
    else:
        # HistoricalDataProvider returns a DataFrame for historical simulation
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

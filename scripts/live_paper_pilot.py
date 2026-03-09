#!/usr/bin/env python3
"""Run a short live paper-trading pilot using `LiveDataProvider`.

This script runs a safe paper-trading loop that polls the exchange for the
latest candle and simulates execution via the execution simulator. It will
stop after `--max-trades` closed trades or after `--duration` seconds.

Usage:
  PYTHONPATH=. python3 scripts/live_paper_pilot.py --duration 600 --max-trades 5 --capital 50
"""
import time
import argparse
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

from paper_trading import PaperTradingSystem
from paper_trading.data_provider import LiveDataProvider
from paper_trading.execution import RealisticExecutionSimulator
from strategies.simple_trend import SimpleTrendStrategy
from risk.engine import RiskEngine


def main(duration: int = 600, max_trades: int = 5, capital: float = 50.0,
         symbol: str = 'BTC/USDT', timeframe: str = '1h', speed: str = 'accelerated'):
    start = datetime.utcnow()
    end_time = start.timestamp() + duration

    provider = LiveDataProvider(symbol=symbol, timeframe=timeframe)
    strategy = SimpleTrendStrategy()
    risk = RiskEngine(capital=capital)
    exec_sim = RealisticExecutionSimulator(min_execution_delay=0.05, max_execution_delay=0.2)

    system = PaperTradingSystem(
        initial_capital=capital,
        symbol=symbol,
        timeframe=timeframe,
        speed=speed,
        data_source='live'
    )

    system.setup(strategy=strategy, risk_engine=risk, data_provider=provider, execution_simulator=exec_sim)

    logging.info('Starting live paper-trading pilot (no real orders will be sent).')

    closed_before = len(system.closed_trades)

    system.is_running = True
    # Run a polling loop that mirrors _run_live_simulation but with limits
    try:
        while datetime.utcnow().timestamp() < end_time and system.is_running:
            latest = provider.get_latest_candle()
            if latest is None:
                time.sleep(1)
                continue

            # Update time and current price
            system.current_time = latest.get('datetime')
            price = latest.get('close')

            # Process existing positions
            try:
                system._process_positions(price, latest)
            except Exception as e:
                logging.error(f'Error processing positions: {e}')

            # Build short historical context for the strategy
            try:
                hist = provider.get_historical_data(limit=200)
                signal = strategy.generate_signal(hist, current_position=system.open_positions[0] if system.open_positions else None)
            except Exception as e:
                logging.error(f'Error generating signal: {e}')
                signal = None

            if signal and getattr(signal, 'signal_type', None):
                try:
                    system._process_signal(signal, price, latest)
                except Exception as e:
                    logging.error(f'Error processing signal: {e}')

            system._update_equity(price)

            # Stop if we've reached max closed trades
            closed_now = len(system.closed_trades)
            if (closed_now - closed_before) >= max_trades:
                logging.info('Reached max_trades target; stopping pilot.')
                break

            time.sleep(1)

    except KeyboardInterrupt:
        logging.info('Pilot interrupted by user')
    finally:
        system.stop()
        # Print summary
        system.print_summary()
        try:
            exec_sim.print_statistics()
        except Exception:
            pass


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--duration', type=int, default=600, help='Max pilot duration in seconds')
    p.add_argument('--max-trades', type=int, default=5, help='Stop after this many closed trades')
    p.add_argument('--capital', type=float, default=50.0)
    p.add_argument('--symbol', type=str, default='BTC/USDT')
    p.add_argument('--timeframe', type=str, default='1h')
    p.add_argument('--speed', type=str, default='accelerated')
    args = p.parse_args()
    main(duration=args.duration, max_trades=args.max_trades, capital=args.capital,
         symbol=args.symbol, timeframe=args.timeframe, speed=args.speed)
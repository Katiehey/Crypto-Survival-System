#!/usr/bin/env python3
import logging
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO)

from paper_trading import PaperTradingSystem
from paper_trading.data_provider import SimulatedDataProvider
from strategies.simple_trend import SimpleTrendStrategy
from risk.engine import RiskEngine
from paper_trading.execution import RealisticExecutionSimulator

# Pilot configuration
DURATION = 300  # seconds
MAX_TRADES = 10
CAPITAL = 100.0
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1h'

provider = SimulatedDataProvider(symbol=SYMBOL, timeframe=TIMEFRAME)
strategy = SimpleTrendStrategy()
risk = RiskEngine(capital=CAPITAL)
exec_sim = RealisticExecutionSimulator(min_execution_delay=0.01, max_execution_delay=0.05)

system = PaperTradingSystem(
    initial_capital=CAPITAL,
    symbol=SYMBOL,
    timeframe=TIMEFRAME,
    speed='accelerated',
    data_source='simulated'
)

system.setup(strategy=strategy, risk_engine=risk, data_provider=provider, execution_simulator=exec_sim)

logging.info('Starting simulated paper-trading pilot (no real orders).')

start = datetime.utcnow()
end_ts = start.timestamp() + DURATION
closed_before = len(system.closed_trades)

system.is_running = True
try:
    while datetime.utcnow().timestamp() < end_ts and system.is_running:
        latest = provider.get_latest_candle()
        if latest is None:
            time.sleep(0.1)
            continue

        system.current_time = latest.get('datetime')
        price = latest.get('close')

        try:
            system._process_positions(price, latest)
        except Exception as e:
            logging.error(f'Error processing positions: {e}')

        try:
            hist = provider.get_historical_data(limit=200)
            # PaperTradingSystem uses `current_capital` to track available cash
            signal = strategy.generate_signal(
                hist,
                current_position=system.open_positions[0] if system.open_positions else None,
                current_capital=system.current_capital
            )
        except Exception as e:
            logging.error(f'Error generating signal: {e}')
            signal = None

        if signal and getattr(signal, 'signal_type', None):
            try:
                system._process_signal(signal, price, latest)
            except Exception as e:
                logging.error(f'Error processing signal: {e}')

        system._update_equity(price)

        closed_now = len(system.closed_trades)
        if (closed_now - closed_before) >= MAX_TRADES:
            logging.info('Reached max_trades target; stopping pilot.')
            break

        time.sleep(0.5)

except KeyboardInterrupt:
    logging.info('Pilot interrupted by user')
finally:
    system.stop()
    system.print_summary()
    try:
        exec_sim.print_statistics()
    except Exception:
        pass

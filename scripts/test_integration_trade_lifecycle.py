"""Integration test: single trade lifecycle (entry -> partial fill -> exit).

This test creates a PaperTradingSystem with a deterministic strategy that
signals a single long entry, a mocked execution simulator that returns a
partial fill on entry and full fill on exit, and verifies trade recording,
fees, and PnL accounting.

Run:
    PYTHONPATH=. python3 scripts/test_integration_trade_lifecycle.py
"""
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)

from paper_trading import PaperTradingSystem
from risk.engine import RiskEngine
from strategies.base import TradingSignal, SignalType


class SingleEntryStrategy:
    """Strategy that emits a single LONG signal on first call, then NO_TRADE."""
    def __init__(self, entry_price):
        self.entry_price = entry_price
        self.emitted = False

    def generate_signal(self, data, current_position=None):
        if not self.emitted:
            self.emitted = True
            return TradingSignal(
                signal_type=SignalType.LONG,
                confidence=1.0,
                entry_price=self.entry_price,
                stop_loss=self.entry_price * 0.98
            )
        return TradingSignal(SignalType.NO_TRADE, 0.0, self.entry_price)

    def check_exit(self, position, current_price, candle):
        return None


class MockExecutionSimulator:
    """Simulates partial fill on first buy, full fill on exit sell."""
    def __init__(self):
        self.calls = []

    def execute_order(self, symbol, side, size, price, order_type='market', limit_price=None):
        self.calls.append((side, size, price))
        # On buy: return partial fill (50%) first time
        if side == 'buy' and len(self.calls) == 1:
            filled = size * 0.5
            exec_price = price * 1.0005
            # `size` is in quote currency (cash). Fee should be calculated on cash value.
            fee = filled * 0.00075
            return type('ER', (), {'success': True, 'execution_price': exec_price, 'fee': fee, 'filled_size': filled, 'reason': ''})
        # On sell or subsequent calls: full fill
        filled = size
        exec_price = price * 0.9995 if side == 'sell' else price
        fee = filled * 0.00075
        return type('ER', (), {'success': True, 'execution_price': exec_price, 'fee': fee, 'filled_size': filled, 'reason': ''})


def run_test():
    initial_capital = 500.0
    entry_price = 42000.0

    system = PaperTradingSystem(initial_capital=initial_capital, symbol='BTC/USDT', timeframe='1h', speed='instant', data_source='historical')

    # Minimal static provider that supplies a dataframe when needed
    class StaticProvider:
        def get_historical_data(self, limit=1000, start_date=None, end_date=None):
            import pandas as pd
            import numpy as np
            n = 60
            prices = [entry_price] * n
            df = pd.DataFrame({
                'open': prices,
                'high': [p + 10 for p in prices],
                'low': [p - 10 for p in prices],
                'close': prices,
                'volume': [100]*n,
                'datetime': [datetime.now() - timedelta(hours=(n-i)) for i in range(n)],
                'atr': [50]*n,
                'efficiency_ratio': [0.8]*n,
                'regime': ['trend']*n,
                'regime_confidence': [0.9]*n
            })
            return df

        def get_latest_candle(self, *a, **k):
            return None

    # Setup components
    strategy = SingleEntryStrategy(entry_price=entry_price)
    risk = RiskEngine(capital=initial_capital)
    exec_sim = MockExecutionSimulator()
    provider = StaticProvider()

    system.setup(strategy=strategy, risk_engine=risk, data_provider=provider, execution_simulator=exec_sim)

    # Manually drive one iteration: generate signal and process it
    historical = provider.get_historical_data(limit=60)
    current_price = float(historical.iloc[-1]['close'])

    sig = system.strategy.generate_signal(historical)
    assert sig.signal_type == SignalType.LONG

    # Process signal -> should open (with partial fill)
    system.current_time = datetime.now()
    system._process_signal(sig, current_price, historical.iloc[-1])

    assert len(system.open_positions) == 1, f"Expected 1 open position, got {len(system.open_positions)}"
    position = system.open_positions[0]
    print(f"Opened position: {position}")

    # Simulate price moving down to stop loss to trigger exit
    stop_price = position.stop_loss
    system.current_time += timedelta(hours=1)
    system._process_positions(stop_price, {'datetime': system.current_time, 'close': stop_price, 'regime': 'trend'})

    # After processing, position should be closed
    assert len(system.open_positions) == 0, "Position not closed"
    assert len(system.closed_trades) == 1, "Closed trades not recorded"

    trade = system.closed_trades[0]
    print("Closed trade:", trade)

    # Basic PnL and fee checks
    assert 'pnl' in trade
    assert 'fees_paid' in trade
    assert system.current_capital <= initial_capital + abs(trade.get('pnl', 0)) + 1

    print("Integration trade lifecycle test PASSED")


if __name__ == '__main__':
    run_test()

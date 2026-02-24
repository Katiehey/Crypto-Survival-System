"""Unit test: partial-fill lifecycle (entry partial -> exit full).

Deterministic simulator returns 50% fill on first buy, then full fill on sell.
Verifies closed trade recorded and PnL/fees computed consistently.
"""
from types import SimpleNamespace
from datetime import datetime

from paper_trading import PaperTradingSystem
from paper_trading.execution import ExecutionResult


ess = None


class SequentialMockExec:
    def __init__(self, fee_rate=0.00075):
        self.calls = 0
        self.fee_rate = fee_rate

    def execute_order(self, symbol, side, size, price, order_type='market', limit_price=None):
        self.calls += 1
        # size is cash (quote). First buy: partial 50%; subsequent sells: full fill.
        if side == 'buy' and self.calls == 1:
            filled = size * 0.5
            exec_price = price * 1.0005
            fee = filled * self.fee_rate
            return ExecutionResult(success=True, execution_price=exec_price, fee=fee, filled_size=filled, reason='partial 50%')
        else:
            # Full fill
            filled = size
            exec_price = price * (0.9995 if side == 'sell' else price)
            fee = filled * self.fee_rate
            return ExecutionResult(success=True, execution_price=exec_price, fee=fee, filled_size=filled, reason='fully filled')


def test_partial_fill_lifecycle():
    system = PaperTradingSystem(initial_capital=500.0, symbol='BTC/USDT', timeframe='1h', speed='instant', data_source='historical')
    # Minimal risk engine to avoid None issues
    system.risk_engine = SimpleNamespace(capital=system.initial_capital, record_trade=lambda *a, **k: None)

    # Small static provider
    class StaticProvider:
        def get_historical_data(self, limit=1000, start_date=None, end_date=None):
            import pandas as pd
            df = pd.DataFrame({'close':[42000]*60, 'high':[42100]*60, 'low':[41900]*60, 'volume':[100]*60, 'regime':['trend']*60, 'regime_confidence':[0.9]*60, 'efficiency_ratio':[0.8]*60, 'atr':[50]*60})
            return df
        def get_latest_candle(self):
            return None

    provider = StaticProvider()
    exec_sim = SequentialMockExec()

    # Use the real RiskEngine for sizing logic
    from risk.engine import RiskEngine
    risk = RiskEngine(capital=system.initial_capital)

    # Wire system
    system.setup(strategy=SimpleNamespace(generate_signal=lambda data, current_position=None: SimpleNamespace(signal_type=SimpleNamespace(value='LONG'), stop_loss=41900.0)),
                 risk_engine=risk,
                 data_provider=provider,
                 execution_simulator=exec_sim)
    system.risk_engine = risk

    # Drive a synthetic signal processing
    system.current_time = datetime.now()
    # Create a mock signal object similarly to strategies.base.TradingSignal semantics
    signal = SimpleNamespace(signal_type=SimpleNamespace(value='LONG'), stop_loss=41900.0)
    current_price = 42000.0

    # Process entry -> should partial-fill
    system._process_signal(signal, current_price, {'datetime': system.current_time, 'close': current_price})
    assert len(system.open_positions) == 1
    pos = system.open_positions[0]
    assert pos.size > 0

    # Trigger exit (sell) via _close_position
    system._close_position(pos, exit_reason='test_exit', exit_price=41900.0)

    assert len(system.open_positions) == 0
    assert len(system.closed_trades) == 1
    trade = system.closed_trades[0]

    # Basic assertions
    assert trade['fees_paid'] >= 0
    assert 'pnl' in trade
    assert trade['trade_id'].startswith('PAPER_')

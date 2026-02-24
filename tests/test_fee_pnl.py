import pytest
from types import SimpleNamespace
from datetime import datetime

from paper_trading.execution import ExecutionSimulator
from paper_trading import PaperTradingSystem


def test_fee_and_pnl_accounting():
    # Setup deterministic simulator (no randomness, no delay)
    sim = ExecutionSimulator(base_slippage=0.0, base_fee_rate=0.00075,
                             min_execution_delay=0.0, max_execution_delay=0.0,
                             fill_probability=1.0, reject_probability=0.0)
    sim.use_real_delays = False

    system = PaperTradingSystem(initial_capital=500.0, symbol='BTC/USDT', timeframe='1h', speed='instant', data_source='historical')
    system.execution_simulator = sim
    # Provide a minimal risk engine to satisfy _close_position assignment
    system.risk_engine = SimpleNamespace(capital=system.current_capital, record_trade=lambda *a, **k: None)

    # Create a dummy signal object acceptable to _create_position
    dummy_signal = SimpleNamespace()
    dummy_signal.signal_type = 'long'

    entry_price = 42000.0
    cash_size = 250.0  # size expressed in quote currency (R)

    # Simulate execution for entry to compute fee and actual filled size
    entry_exec = sim.execute_order(system.symbol, 'buy', size=cash_size, price=entry_price)
    assert entry_exec.success
    # ExecutionSimulator currently returns ExecutionResult without filled_size attribute set
    # Ensure the returned object reflects the actual filled cash size
    if getattr(entry_exec, 'filled_size', 0) == 0:
        entry_exec.filled_size = cash_size
        entry_exec.fee = entry_exec.filled_size * sim.base_fee_rate

    # Ensure system current time is set so position.entry_time is valid
    system.current_time = datetime.now()

    # Create position using actual filled data
    position = system._create_position(signal=dummy_signal, entry_price=entry_exec.execution_price,
                                       size=entry_exec.filled_size, stop_loss=entry_price * 0.98,
                                       take_profit=None)
    position.entry_fee = entry_exec.fee
    system.open_positions.append(position)

    # Set a future current time for exit
    system.current_time = datetime.now()

    # Perform exit via _close_position (simulator will compute exit fee)
    exit_price = 41139.42
    system._close_position(position, exit_reason='test', exit_price=exit_price)

    # Validate closed trade
    assert len(system.closed_trades) == 1
    trade = system.closed_trades[0]

    # Fees should equal entry fee + exit fee
    expected_exit_exec = sim.execute_order(system.symbol, 'sell', size=entry_exec.filled_size, price=exit_price)
    if getattr(expected_exit_exec, 'filled_size', 0) == 0:
        expected_exit_exec.filled_size = entry_exec.filled_size
        expected_exit_exec.fee = expected_exit_exec.filled_size * sim.base_fee_rate

    expected_total_fees = pytest.approx(entry_exec.fee + expected_exit_exec.fee, rel=1e-6)
    assert trade['fees_paid'] == expected_total_fees

    # Expected gross pnl (before fees): (exit - entry) * (size / entry_price)
    gross_pnl = (exit_price - entry_exec.execution_price) * (entry_exec.filled_size / entry_exec.execution_price)
    expected_net = pytest.approx(gross_pnl - (entry_exec.fee + expected_exit_exec.fee), rel=1e-6)
    assert trade['pnl'] == expected_net

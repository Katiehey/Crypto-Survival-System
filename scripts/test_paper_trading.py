# scripts/test_paper_trading.py
"""
Test the complete paper trading system.
"""

import sys
import os
import logging
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from paper_trading import PaperTradingSystem
from paper_trading.data_provider import create_data_provider
from paper_trading.execution import create_execution_simulator
from strategies.simple_trend import SimpleTrendStrategy
from risk.engine import RiskEngine
from strategies.base import TradingSignal, SignalType


class MockStrategy(SimpleTrendStrategy):
    """Mock strategy for testing."""
    
    def generate_signal(self, data, current_position=None):
        """Generate alternating buy/sell signals for testing."""
        if len(data) < 50:
            return None
        
        # Alternate between buy and sell every 10 candles
        candle_index = len(data) - 1
        if candle_index % 20 < 10:
            from strategies.base import TradingSignal, SignalType
            return TradingSignal(
                signal_type=SignalType.LONG,
                entry_price=data['close'].iloc[-1],
                confidence=0.7,
                reason="Test buy signal"
            )
        else:
            from strategies.base import TradingSignal, SignalType
            return TradingSignal(
                signal_type=SignalType.SHORT,
                entry_price=data['close'].iloc[-1],
                confidence=0.6,
                reason="Test sell signal"
            )
    
    def check_exit(self, position, current_price, candle):
        """Exit after 5 candles or 2% profit/loss."""
        from datetime import datetime
        
        # Calculate position age
        current_time = candle['datetime']
        position_age = current_time - position.entry_time
        
        # Exit if position is old (for testing)
        if position_age.total_seconds() >= 5 * 3600: 
            return "time_exit"
        
        # Calculate PnL
        if position.side == 'long':
            pnl_pct = (current_price - position.entry_price) / position.entry_price * 100
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price * 100
        
        # Take profit at 2%
        if pnl_pct >= 2.0:
            return "take_profit"
        
        # Stop loss at -1.5%
        if pnl_pct <= -1.5:
            return "stop_loss"
        
        return None


def test_basic_paper_trading():
    """Test basic paper trading functionality."""
    print("=" * 70)
    print("BASIC PAPER TRADING TEST")
    print("=" * 70)
    
    # Create paper trading system
    system = PaperTradingSystem(
        initial_capital=1000,
        symbol="BTC/USDT",
        timeframe="1h",
        speed="instant",  # No delays for testing
        data_source="historical"
    )
    
    # Create components
    strategy = MockStrategy()
    
    risk_engine = RiskEngine(capital=1000)
    
    data_provider = create_data_provider(
        "simulated",
        symbol="BTC/USDT",
        timeframe="1h",
        initial_price=42000
    )
    
    execution_simulator = create_execution_simulator(
        "basic",
        base_slippage=0.001,
        base_fee_rate=0.00075,
        min_execution_delay=0.01,
        max_execution_delay=0.05
    )
    
    # Setup system
    system.setup(
        strategy=strategy,
        risk_engine=risk_engine,
        data_provider=data_provider,
        execution_simulator=execution_simulator
    )

    system.is_running = True
    
    # Run with limited historical data
    print("\n🚀 Starting paper trading simulation...")
    
    # We'll manually simulate a few steps for testing
    test_steps = 150
    
    for step in range(test_steps):
        if not system.is_running:
            print(f"⚠️ System stopped at step {step}. Check for errors.")
            break
        
        # Get historical data up to this point
        data = data_provider.get_historical_data(limit=step + 100)
        
        if len(data) < 50:
            continue
        
        current_candle = data.iloc[-1].to_dict()
        current_price = current_candle['close']
        system.current_time = current_candle['datetime']
        
        # Process existing positions
        for position in system.open_positions[:]:
            # Check exit conditions
            exit_signal = strategy.check_exit(position, current_price, current_candle)
            if exit_signal:
                system._close_position(position, exit_signal, current_price)
        
        # Generate and process signal (every 10th step)
        if step % 10 == 0 and len(system.open_positions) == 0:
            signal = strategy.generate_signal(data, None)
            if signal and signal.signal_type != 'NO_TRADE':
                system._process_signal(signal, current_price, current_candle)
        
        # Update equity
        system._update_equity(current_price)
        
        if step % 10 == 0:
            regime = current_candle.get('regime', 'unknown')
            print(f"   Step {step:3d} | Regime: {regime:7s} | Capital: R{system.current_capital:.2f} | "
                  f"Pos: {len(system.open_positions)} | Trades: {len(system.closed_trades)}")
    
    # Stop system
    system.stop()
    
    # Print summary
    print("\n" + "=" * 70)
    print("SIMULATION RESULTS")
    print("=" * 70)
    
    system.print_summary()
    
    # Print execution statistics
    if execution_simulator:
        print("\n" + "=" * 70)
        execution_simulator.print_statistics()
    
    return system


def test_historical_replay():
    """Test paper trading with historical data replay."""
    print("\n" + "=" * 70)
    print("HISTORICAL REPLAY TEST")
    print("=" * 70)
    
    try:
        # Try to use real historical data
        from data.fetcher import DataFetcher
        
        fetcher = DataFetcher()
        count = fetcher.get_candle_count()
        
        if count < 100:
            print("⚠️  Insufficient historical data. Skipping historical replay test.")
            return None
        
        print(f"📊 Found {count} candles of historical data")
        
        # Create paper trading system for historical replay
        system = PaperTradingSystem(
            initial_capital=500,
            symbol="BTC/USDT",
            timeframe="1h",
            speed="instant",  # No delays for testing
            data_source="historical"
        )
        
        # Create components
        strategy = SimpleTrendStrategy()
        risk_engine = RiskEngine(capital=500)
        
        data_provider = create_data_provider(
            "historical",
            symbol="BTC/USDT",
            timeframe="1h"
        )
        
        # Setup system
        system.setup(
        strategy=strategy,
        risk_engine=risk_engine,
        data_provider=data_provider
    )
    
        print("🚀 Starting historical replay...")

        historical_data = data_provider.get_historical_data(limit=1000)
        
        if historical_data is not None and not historical_data.empty:
            system.is_historical = True
            system.initial_sim_time = historical_data.iloc[0]['datetime']
            logger.info(f"✅ Simulation anchor set to: {system.initial_sim_time}")
        else:
            print("⚠️ Could not retrieve historical data for replay.")

    # CALL START TO ACTUALLY RUN THE SIMULATION
        system.start() 
    
    # PRINT RESULTS AFTER START FINISHES
        print("\n" + "=" * 70)
        print("HISTORICAL REPLAY SUMMARY")
        print("=" * 70)
        system.print_summary()
        
        # Note: Full historical replay would take time
        # We'll run a limited version
        return system
        
    except ImportError:
        print("⚠️  DataFetcher not available. Skipping historical replay.")
        return None
    except Exception as e:
        print(f"⚠️  Error in historical replay: {e}")
        return None


def test_performance_analysis():
    """Test performance analysis of paper trading results."""
    print("\n" + "=" * 70)
    print("PERFORMANCE ANALYSIS TEST")
    print("=" * 70)
    
    # Run a basic paper trading test
    system = test_basic_paper_trading()
    
    if not system or not system.closed_trades:
        print("⚠️  No trades to analyze")
        return
    
    # Convert trades to DataFrame for analysis
    trades_df = pd.DataFrame(system.closed_trades)
    
    print(f"\n📈 TRADE ANALYSIS")
    print(f"   Total Trades: {len(trades_df)}")
    print(f"   Winning Trades: {len(trades_df[trades_df['pnl'] > 0])}")
    print(f"   Losing Trades: {len(trades_df[trades_df['pnl'] <= 0])}")
    print(f"   Total PnL: R{trades_df['pnl'].sum():.2f}")
    print(f"   Avg PnL: R{trades_df['pnl'].mean():.2f}")
    print(f"   Win Rate: {len(trades_df[trades_df['pnl'] > 0]) / len(trades_df):.1%}")
    
    # Calculate basic metrics
    winning_trades = trades_df[trades_df['pnl'] > 0]
    losing_trades = trades_df[trades_df['pnl'] <= 0]
    
    if len(winning_trades) > 0:
        avg_win = winning_trades['pnl'].mean()
        print(f"   Avg Win: R{avg_win:.2f}")
    
    if len(losing_trades) > 0:
        avg_loss = losing_trades['pnl'].mean()
        print(f"   Avg Loss: R{avg_loss:.2f}")
    
    # Calculate profit factor
    if len(losing_trades) > 0:
        total_wins = winning_trades['pnl'].sum()
        total_losses = abs(losing_trades['pnl'].sum())
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        print(f"   Profit Factor: {profit_factor:.2f}")
    
    # Analyze by exit reason
    print(f"\n🎯 EXIT REASON ANALYSIS")
    for reason in trades_df['exit_reason'].unique():
        reason_trades = trades_df[trades_df['exit_reason'] == reason]
        if len(reason_trades) > 0:
            avg_pnl = reason_trades['pnl'].mean()
            win_rate = len(reason_trades[reason_trades['pnl'] > 0]) / len(reason_trades)
            print(f"   {reason:15s}: {len(reason_trades):2d} trades, "
                  f"Avg PnL: R{avg_pnl:+.2f}, Win Rate: {win_rate:.1%}")


def main():
    """Run all paper trading tests."""
    print("=" * 70)
    print("COMPLETE PAPER TRADING TEST SUITE")
    print("=" * 70)
    
    # Test 1: Basic functionality
    test_basic_paper_trading()
    
    # Test 2: Historical replay (if data available)
    test_historical_replay()
    
    # Test 3: Performance analysis
    test_performance_analysis()
    
    print("\n" + "=" * 70)
    print("✅ PAPER TRADING TEST SUITE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
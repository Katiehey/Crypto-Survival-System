# paper_trading/__init__.py
"""
Paper trading system for risk-free strategy testing.
Simulates live trading with historical or real-time data.
"""

from datetime import datetime, timedelta
from strategies.base import Strategy, TradingSignal, SignalType
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)
# Import exchange minimum from RiskEngine for consistent minimum-notional enforcement
from risk.engine import EXCHANGE_MIN_ZAR


class PaperTradingSystem:
    """
    Paper trading system for simulating live trading.
    
    Features:
    - Real-time or accelerated time simulation
    - Historical data replay with execution delays
    - Complete trade simulation with realistic execution
    - Risk engine integration
    - Performance tracking
    - No real capital at risk
    """
    
    def __init__(
        self,
        initial_capital: float = 500,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        speed: str = "realtime",  # 'realtime', 'accelerated', 'instant'
        data_source: str = "historical"  # 'historical', 'live'
    ):
        """
        Initialize paper trading system.
        
        Args:
            initial_capital: Starting paper capital
            symbol: Trading pair
            timeframe: Candle timeframe
            speed: Simulation speed
            data_source: Data source for simulation
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.symbol = symbol
        self.timeframe = timeframe
        self.speed = speed
        self.data_source = data_source
        
        # State tracking
        self.open_positions = []
        self.closed_trades = []
        # Initialize equity history with a consistent schema
        self.equity_history = [{
            'timestamp': datetime.now(),
            'capital': initial_capital,
            'cash': initial_capital,
            'position_value': 0.0,
            'open_positions': 0
        }]
        self.current_time = None
        self.is_running = False
        
        # Components (will be initialized later)
        self.strategy = None
        self.risk_engine = None
        self.data_provider = None
        self.execution_simulator = None
        self.is_historical = False  # Default to False
        self.last_update_time = datetime.now()
        
        logger.info(f"PaperTradingSystem initialized: {symbol} {timeframe}, "
                   f"Capital: R{initial_capital}, Speed: {speed}")
    
    def setup(
        self,
        strategy,
        risk_engine,
        data_provider,
        execution_simulator=None
    ):
        """
        Set up paper trading system with components.
        
        Args:
            strategy: Trading strategy instance
            risk_engine: Risk engine instance
            data_provider: Data provider for market data
            execution_simulator: Execution simulator (optional)
        """
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.data_provider = data_provider
        self.execution_simulator = execution_simulator
        
        # Initialize risk engine with paper capital
        self.risk_engine.capital = self.current_capital

        
        logger.info("Paper trading system setup complete")
    
    def start(self, start_time: Optional[datetime] = None):
        """
        Start paper trading simulation.
        
        Args:
            start_time: Simulation start time (defaults to now for live, or historical start)
        """
        if not all([self.strategy, self.risk_engine, self.data_provider]):
            raise ValueError("Paper trading system not fully configured")
        
        self.is_running = True
        self.current_time = start_time or datetime.now()
        
        # Initialize equity history
        self.equity_history.append({
            'timestamp': self.current_time,
            'capital': self.current_capital,
            'open_positions': len(self.open_positions)
        })
        
        logger.info(f"Paper trading started at {self.current_time}")
        
        # Start the main loop based on data source
        if self.data_source == "historical":
            self._run_historical_simulation()
        else:
            self._run_live_simulation()
    
    def stop(self):
        """Stop paper trading simulation."""
        self.is_running = False
        
        # Close any open positions
        for position in self.open_positions[:]:
            self._close_position(position, "system_stop")
        
        logger.info(f"Paper trading stopped. Final capital: R{self.current_capital:.2f}")
    
    def _run_historical_simulation(self):
        """Run paper trading with historical data."""
        logger.info("Starting historical paper trading simulation...")
        
        # Get historical data
        historical_data = self.data_provider.get_historical_data(
            limit=1000
        )
        
        # Process each candle in sequence
        for i, candle in historical_data.iterrows():
            # Global file-based kill switch: create a file named STOP_TRADING in repo root to abort
            try:
                import os
                if os.path.exists('STOP_TRADING'):
                    logger.critical('STOP_TRADING file detected — aborting paper trading run')
                    self.is_running = False
                    break
            except Exception:
                pass
            if not self.is_running:
                break
            
            self.current_time = candle['datetime']
            
            # Update market data
            current_price = candle['close']
            
            # Process existing positions
            self._process_positions(current_price, candle)
            
            # Get strategy signal
            signal = self.strategy.generate_signal(
                historical_data.iloc[:i+1],  # Only data up to current
                current_position=self.open_positions[0] if self.open_positions else None
            )
            
            # Process signal
            if signal and signal.signal_type != 'NO_TRADE':
                self._process_signal(signal, current_price, candle)
            
            # Update equity tracking
            self._update_equity(current_price)
            
            # Simulate time delay based on speed
            self._simulate_time_delay()
        
        # End of simulation
        self.stop()
    
    def _run_live_simulation(self):
        """Run paper trading with live data."""
        logger.info("Starting live paper trading simulation...")
        
        # This would connect to live data feed
        # For now, we'll implement a skeleton
        while self.is_running:
            try:
                # Get latest candle from live data (data provider API doesn't accept kwargs)
                latest_candle = self.data_provider.get_latest_candle()
                
                if latest_candle is None:
                    continue
                
                self.current_time = latest_candle['datetime']
                current_price = latest_candle['close']
                
                # Process existing positions
                self._process_positions(current_price, latest_candle)
                
                # Get strategy signal (would use recent data)
                # signal = self.strategy.generate_signal(...)
                
                # Update equity
                self._update_equity(current_price)
                
                # Sleep based on timeframe
                self._simulate_time_delay()
                
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error in live simulation: {e}")
                continue
    
    def _process_positions(self, current_price: float, candle: dict):
        """Process existing open positions."""
        for position in self.open_positions[:]:  # Copy list for safe removal
            # Check stop loss
            if position.stop_loss and current_price <= position.stop_loss:
                self._close_position(position, "stop_loss", current_price)
                continue
            
            # Check take profit
            if position.take_profit and current_price >= position.take_profit:
                self._close_position(position, "take_profit", current_price)
                continue
            
            # Check strategy exit
            exit_signal = self.strategy.check_exit(position, current_price, candle)
            if exit_signal:
                self._close_position(position, exit_signal, current_price)
                continue
            
            # Update position metrics
            position.update_metrics(current_price)
    
    def _process_signal(self, signal, current_price: float, candle: dict):
        """Process trading signal."""

        if str(signal.signal_type).split('.')[-1] == "NO_TRADE":
            return

        # 1. Get current regime from the candle
        current_regime = candle.get('regime', 'trend')

        # 2. Risk Engine sizing (Returns size in Quote Currency, e.g., R-Rand or USDT)
        pos_calc = self.risk_engine.calculate_position_size(
            entry_price=current_price,
            stop_loss_price=signal.stop_loss or (current_price * 0.98),
            regime=current_regime
        )

        # Normal sizing info logged at debug when enabled

        if not pos_calc.is_valid or pos_calc.size <= 0:
            logger.info(f"Signal rejected: {pos_calc.reason}")
            if "Daily loss limit" in pos_calc.reason or "Kill switch" in pos_calc.reason:
                logger.critical("🚨 SACRED LIMIT BREACHED. Shutting down system.")
                self.is_running = False
            return

        # Enforce minimum trade notional to avoid micro-trades on small accounts
        try:
            min_notional = EXCHANGE_MIN_ZAR
            if pos_calc.size < min_notional:
                logger.info(f"Signal rejected: Calculated size R{pos_calc.size:.2f} below exchange minimum R{min_notional:.2f}")
                return
        except Exception:
            # If something goes wrong reading the min, continue with existing flow
            pass
        
        # 3. Execution Simulation (The FIX happens here)
            if self.execution_simulator:
            # We pass pos_calc.size (The Rand/Dollar amount)
                # Normalize side to 'buy'/'sell' for simulators
                raw_side = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
                raw_side = raw_side.lower()
                if raw_side in ('long', 'buy'):
                    side = 'buy'
                elif raw_side in ('short', 'sell'):
                    side = 'sell'
                else:
                    side = raw_side

                execution = self.execution_simulator.execute_order(
                    symbol=self.symbol,
                    side=side,
                    size=pos_calc.size,  # Correctly passing the "Cash" size
                    price=current_price
                )
            
            # THE FIX: Trust the success boolean, not reason strings
            if not execution.success:
                logger.warning(f"❌ Execution failed: {execution.reason}")
                return

            # Use ACTUAL data from the simulator result
            final_size = getattr(execution, 'filled_size', None)
            final_price = getattr(execution, 'execution_price', None)
            final_fee = getattr(execution, 'fee', None)
        else:
            # Fallback if no simulator is attached
            final_size = pos_calc.size
            final_price = current_price
            final_fee = 0.0

        # 4. Create position with ACTUAL filled data
        position = self._create_position(
            signal=signal,
            entry_price=final_price,
            size=final_size,
            stop_loss=signal.stop_loss or (final_price * 0.98),
            take_profit=self._calculate_take_profit(signal, final_price, candle)
        )
        position.entry_fee = final_fee
        # Attach risk sizing metadata so closes can report to RiskEngine
        try:
            position.risk_amount = pos_calc.risk_amount
        except Exception:
            position.risk_amount = 0.0
        
        # 5. Update State (Atomic operation)
        self.open_positions.append(position)
        self.current_capital -= (final_size + final_fee) # Deduct size + fees

        self.risk_engine.capital = self.current_capital

        # Debug log to verify the math
        crypto_units = final_size / final_price
        logger.info(f"✅ PAPER {signal.signal_type} OPEN: {crypto_units:.8f} Units @ {final_price:.2f} | Fee: {final_fee:.4f}")
        print(f"DEBUG: Size={final_size}, Price={final_price}, Math={crypto_units}")
    
    def _create_position(self, signal, entry_price: float, size: float, 
                        stop_loss: Optional[float], take_profit: Optional[float]):
        """Create a new position object."""
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class PaperPosition:
            id: str
            symbol: str
            side: str
            entry_price: float
            size: float
            entry_time: datetime
            stop_loss: Optional[float]
            take_profit: Optional[float]
            current_price: float
            current_pnl: float = 0.0
            current_pnl_percent: float = 0.0
            max_favorable: float = 0.0
            max_adverse: float = 0.0
            
            def update_metrics(self, current_price: float):
                """Update position metrics."""
                self.current_price = current_price
                
                if self.side in ('long', 'buy'):
                    self.current_pnl = (current_price - self.entry_price) * (self.size / self.entry_price)
                else:  # short / sell
                    self.current_pnl = (self.entry_price - current_price) * (self.size / self.entry_price)
                
                self.current_pnl_percent = (self.current_pnl / self.size) * 100
                
                # Update MFE/MAE
                if self.side in ('long', 'buy'):
                    self.max_favorable = max(self.max_favorable, current_price - self.entry_price)
                    self.max_adverse = min(self.max_adverse, current_price - self.entry_price)
                else:
                    self.max_favorable = max(self.max_favorable, self.entry_price - current_price)
                    self.max_adverse = min(self.max_adverse, self.entry_price - current_price)
            
            def __repr__(self):
                return (f"PaperPosition({self.side} {self.symbol} "
                       f"@{self.entry_price:.2f}, "
                       f"Size: R{self.size:.2f}, "
                       f"PnL: R{self.current_pnl:+.2f})")
        
        position_id = f"PAPER_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.closed_trades) + 1}"
        
        raw_side = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
        raw_side = raw_side.lower()
        if raw_side in ('long', 'buy'):
            side = 'buy'
        elif raw_side in ('short', 'sell'):
            side = 'sell'
        else:
            side = raw_side

        return PaperPosition(
            id=position_id,
            symbol=self.symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            entry_time=self.current_time,
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_price=entry_price
        )
    
    def _close_position(self, position, exit_reason: str, exit_price: Optional[float] = None):
        """Close an open position."""
        if exit_price is None:
            exit_price = position.current_price
        
        # Simulate exit execution first so we compute PnL using the actual filled price
        exit_fee = 0.0
        if self.execution_simulator:
            # Map logical position side to execution side
            exec_side = 'sell' if position.side in ('long', 'buy') else 'buy'
            execution = self.execution_simulator.execute_order(
                symbol=self.symbol,
                side=exec_side,
                size=position.size,
                price=exit_price
            )

            if execution.success:
                # Use actual execution values
                exit_price = execution.execution_price
                exit_fee = execution.fee
            else:
                logger.warning(f"Exit execution failed: {execution.reason}")

        # Calculate final (gross) PnL using the final exit price
        if position.side in ('long', 'buy'):
            pnl = (exit_price - position.entry_price) * (position.size / position.entry_price)
        else:
            pnl = (position.entry_price - exit_price) * (position.size / position.entry_price)
        
        # Calculate fees and net PnL for recording (fees include entry + exit)
        entry_fee = (position.entry_fee if hasattr(position, 'entry_fee') else 0.0)
        total_fees = entry_fee + exit_fee

        # net_pnl is the realized PnL after all fees (used for records and risk accounting)
        net_pnl = pnl - total_fees

        pnl_percent = 0.0
        if position.size > 0:
            pnl_percent = (net_pnl / position.size) * 100

        # Update capital: entry already deducted entry_fee and size at open.
        # On close we add back the position notional and the gross pnl, then subtract the exit fee.
        # This yields the same final capital as applying net_pnl once.
        self.current_capital += position.size + pnl - exit_fee

        self.risk_engine.capital = self.current_capital

        # Record trade outcome with RiskEngine so daily limits / cooldowns apply
        try:
            risk_amt = getattr(position, 'risk_amount', 0.0)
            # Use net_pnl (after both fees) for risk accounting
            self.risk_engine.record_trade(pnl=net_pnl, risk_amount=risk_amt, current_time=self.current_time)
        except Exception:
            # Non-fatal: continue even if risk engine recording fails
            logger.exception("Failed to record trade in RiskEngine")
        
        # Create trade record
        trade = {
            'trade_id': position.id,
            'entry_time': position.entry_time,
            'exit_time': self.current_time,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'side': position.side,
            'size': position.size,
            'pnl': net_pnl,
            'pnl_percent': pnl_percent,
            'exit_reason': exit_reason,
            'fees_paid': total_fees,
            'duration_hours': (self.current_time - position.entry_time).total_seconds() / 3600,
            'max_favorable': position.max_favorable,
            'max_adverse': position.max_adverse
        }
        
        # Add to closed trades
        self.closed_trades.append(trade)
        
        # Remove from open positions
        self.open_positions.remove(position)
        
        logger.info(f"Position closed: {position.id}, "
                   f"Reason: {exit_reason}, "
                   f"PnL: R{net_pnl:+.2f}")
    
    def _calculate_stop_loss(self, signal, current_price: float, candle: dict) -> Optional[float]:
        """Calculate stop loss price."""
        # This would use ATR or other volatility measures
        # For now, use a simple percentage
        if signal.signal_type == 'LONG':
            return current_price * 0.98  # 2% stop loss
        else:
            return current_price * 1.02  # 2% stop loss for shorts
    
    def _calculate_take_profit(self, signal, current_price: float, candle: dict) -> Optional[float]:
        """Calculate take profit price."""
        # Simple risk-reward ratio
        stop_loss = self._calculate_stop_loss(signal, current_price, candle)
        
        if stop_loss and signal.signal_type == 'LONG':
            risk = current_price - stop_loss
            return current_price + (risk * 2)  # 2:1 reward:risk
        elif stop_loss:
            risk = stop_loss - current_price
            return current_price - (risk * 2)
        
        return None
    
    def _update_equity(self, current_price: float):
        """Update equity history."""
        # 1. Handle Initialization of last_update_time
        if not hasattr(self, 'last_update_time') or self.last_update_time is None:
            self.last_update_time = self.current_time - timedelta(seconds=1)

    # 2. Strict Increasing Check: If data provider is stuck or resets, force a step
        if self.current_time <= self.last_update_time:
        # Step forward by 1 hour (matching your system timeframe)
            self.current_time = self.last_update_time + timedelta(hours=1)
    
        self.last_update_time = self.current_time

    # 3. Calculate Valuation
        total_position_value = sum(
            p.size + p.current_pnl for p in self.open_positions
        )
    
        total_equity = self.current_capital + total_position_value

    # 4. Sync Risk Engine
        self.risk_engine.capital = self.current_capital
    
    # 5. Record History
        self.equity_history.append({
        'timestamp': self.current_time,
        'capital': total_equity,
        'open_positions': len(self.open_positions),
        'cash': self.current_capital,
        'position_value': total_position_value
    })
    
    def _simulate_time_delay(self):
        """Simulate time delay based on speed setting."""
        import time
        
        if self.speed == 'instant':
            return  # No delay
        elif self.speed == 'accelerated':
            time.sleep(0.1)  # 100ms delay
        elif self.speed == 'realtime':
            # Wait for next candle based on timeframe
            if self.timeframe == '1h':
                time.sleep(3600)  # 1 hour
            elif self.timeframe == '15m':
                time.sleep(900)  # 15 minutes
            elif self.timeframe == '5m':
                time.sleep(300)  # 5 minutes
            elif self.timeframe == '1m':
                time.sleep(60)  # 1 minute
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary of paper trading session."""
        total_trades = len(self.closed_trades)
        winning_trades = [t for t in self.closed_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in self.closed_trades if t.get('pnl', 0) <= 0]
    
        peak_cap = max((h['capital'] for h in self.equity_history), default=self.initial_capital)
        valid_history = [h for h in self.equity_history if h['timestamp'] is not None]
    
    # Base dictionary with all required keys (default values)
        summary = {
        'total_trades': total_trades,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': len(winning_trades) / total_trades if total_trades > 0 else 0,
        'total_pnl': sum(t.get('pnl', 0) for t in self.closed_trades),
        'total_return_pct': ((self.current_capital / self.initial_capital) - 1) * 100,
        'avg_win': sum(t.get('pnl', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0,
        'avg_loss': sum(t.get('pnl', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0,
        'largest_win': max((t.get('pnl', 0) for t in winning_trades), default=0),
        'largest_loss': min((t.get('pnl', 0) for t in losing_trades), default=0),
        'current_capital': self.current_capital,
        'peak_capital': peak_cap,
        'current_drawdown': ((peak_cap - self.current_capital) / peak_cap * 100) if peak_cap > 0 else 0,
        'open_positions': len(self.open_positions),
        'start_time': self.initial_sim_time if (hasattr(self, 'is_historical') and self.is_historical) else (valid_history[0]['timestamp'] if valid_history else self.start_time),
        'end_time': self.current_time
    }
    
        return summary
    
    def print_summary(self):
        """Print formatted performance summary."""
        summary = self.get_performance_summary()
        
        print("=" * 70)
        print("PAPER TRADING SUMMARY")
        print("=" * 70)
        
        print(f"\n💰 CAPITAL")
        print(f"   Initial: R{self.initial_capital:.2f}")
        print(f"   Current: R{summary['current_capital']:.2f}")
        print(f"   Peak:    R{summary['peak_capital']:.2f}")
        print(f"   Return:  R{summary['total_pnl']:+.2f} ({summary['total_return_pct']:+.2f}%)")
        
        print(f"\n📊 TRADES")
        print(f"   Total:   {summary['total_trades']}")
        print(f"   Wins:    {summary['winning_trades']}")
        print(f"   Losses:  {summary['losing_trades']}")
        print(f"   Win Rate: {summary['win_rate']:.1%}")
        
        if summary['total_trades'] > 0:
            print(f"\n📈 PERFORMANCE")
            print(f"   Avg Win:  R{summary['avg_win']:.2f}")
            print(f"   Avg Loss: R{summary['avg_loss']:.2f}")
            print(f"   Largest Win:  R{summary['largest_win']:.2f}")
            print(f"   Largest Loss: R{summary['largest_loss']:.2f}")
            
            if summary['losing_trades'] > 0 and summary['avg_loss'] != 0:
                gross_profits = summary['avg_win'] * summary['winning_trades']
                gross_losses = abs(summary['avg_loss'] * summary['losing_trades'])
                profit_factor = gross_profits / gross_losses if gross_losses > 0 else 0
                print(f"   Profit Factor: {profit_factor:.2f}")
            else:
                print(f"   Profit Factor: n/a")
            
        
        print(f"\n⚠️  RISK")
        print(f"   Current Drawdown: {summary['current_drawdown']:.2f}%")
        print(f"   Open Positions: {summary['open_positions']}")
        
        print(f"\n⏰ TIMING")
        print(f"   Started:  {summary['start_time']}")
        print(f"   Ended:    {summary['end_time']}")
        if summary['start_time'] and summary['end_time']:
            duration = (summary['end_time'] - summary['start_time'])
            print(f"   Duration: {duration}")
        
        print("\n" + "=" * 70)


def main():
    """Test paper trading system."""
    print("=" * 70)
    print("PAPER TRADING SYSTEM TEST")
    print("=" * 70)
    
    # Create paper trading system
    system = PaperTradingSystem(
        initial_capital=500,
        symbol="BTC/USDT",
        timeframe="1h",
        speed="instant",  # No delays for testing
        data_source="historical"
    )
    
    # Print system info
    print(f"\n📋 System Configuration:")
    print(f"   Symbol: {system.symbol}")
    print(f"   Timeframe: {system.timeframe}")
    print(f"   Initial Capital: R{system.initial_capital}")
    print(f"   Speed: {system.speed}")
    print(f"   Data Source: {system.data_source}")
    
    # Note: Full testing requires strategy, risk engine, and data provider
    # This will be implemented in the next steps
    
    print("\n✅ Paper trading system initialized successfully")
    print("=" * 70)


if __name__ == "__main__":
    main()
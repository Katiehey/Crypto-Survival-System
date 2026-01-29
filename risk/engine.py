"""
Risk Engine - Capital Preservation System

The risk engine is the guardian of capital. It calculates position sizes,
validates trades against risk limits, and enforces safety constraints.

This is THE most critical component of the system. Every calculation
must be mathematically correct. No shortcuts.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Tuple, Optional

from config.system_config import RISK_LIMITS
from risk.capital_tracker import CapitalTracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# EXCHANGE_MIN_ZAR: Approx $10 minimum notional requirement for most exchanges
# This prevents the bot from attempting orders that will be rejected.
EXCHANGE_MIN_ZAR = 50.0

@dataclass
class TradeState:
    """
    Current trading state for risk tracking.
    Tracks daily limits, consecutive losses, and kill switch status.
    """
    current_date: date = field(default_factory=lambda: datetime.now().date())
    trades_today: int = 0
    daily_loss: float = 0.0
    consecutive_losses: int = 0
    last_trade_result: Optional[str] = None  # 'win' or 'loss'
    cooldown_until: Optional[datetime] = None
    kill_switch_active: bool = False
    kill_switch_reason: str = ""

    def reset_daily(self) -> None:
        """Reset daily counters (called at midnight)."""
        self.current_date = datetime.now().date()
        self.trades_today = 0
        self.daily_loss = 0.0
    
    def is_in_cooldown(self, current_time: Optional[datetime] = None) -> bool:
        if self.cooldown_until is None:
            return False
    # Use provided time (backtest) or system time (live)
        check_time = current_time if current_time else datetime.now()
        return check_time < self.cooldown_until
    
    def activate_cooldown(self, hours: int = 24) -> None:
        """
        Activate cooldown period.
        
        Args:
            hours: Cooldown duration in hours
        """
        self.cooldown_until = datetime.now() + timedelta(hours=hours)
        
        logger.warning(
            f"Cooldown activated until {self.cooldown_until.isoformat()}"
        )
    
    def clear_cooldown(self) -> None:
        """Clear cooldown period."""
        if self.cooldown_until:
            logger.info("Cooldown period cleared")
        self.cooldown_until = None


@dataclass
class PositionSize:
    """
    Result of position sizing calculation.
    """
    size: float
    risk_amount: float
    risk_percent: float
    stop_distance_percent: float
    is_valid: bool
    reason: str = "OK"

    def __repr__(self):
        """Return a string representation of the position size."""
        return (f"PositionSize(size={self.size:.2f}, risk={self.risk_amount:.2f}, "
                f"valid={self.is_valid}, reason='{self.reason}')")


class RiskEngine:
    """
    Core risk management engine.
    """
    
    def __init__(self, capital: float):
        """
        Initialize risk engine.
        
        Args:
            capital: Current trading capital
            
        Raises:
            ValueError: If capital is invalid
        """
        if capital <= 0:
            raise ValueError(f"Capital must be positive, got {capital}")
        
        self.capital = capital
        self.state = TradeState()
        # Integration of the Capital Tracker for equity curve/drawdown monitoring
        self.capital_tracker = CapitalTracker(starting_capital=capital)
        
        logger.info(f"RiskEngine initialized with capital: R{capital:.2f}")

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        risk_percent: Optional[float] = None,
        regime: str = "trend"
    ) -> PositionSize:
        """Calculate position size and validate against all risk limits."""
        
        # Use default risk if not specified
        if risk_percent is None:
            risk_percent = RISK_LIMITS.MAX_RISK_PER_TRADE

        # 🧠 REGIME-BASED RISK SCALING
        # If the market is in 'chaos', we cut our risk in half to preserve capital
        if regime == 'chaos':
            risk_percent = risk_percent * 0.5
            logger.info(f"🛡️ Chaos detected: Scaling risk down to {risk_percent*100:.2f}%")
        
        # 1. Price/Input Validation
        valid_input, reason = self._validate_inputs(entry_price, stop_loss_price, risk_percent)
        if not valid_input:
            return PositionSize(0.0, 0.0, risk_percent, 0.0, False, reason)
        
        # 2. Mathematical Calculations
        risk_amount = self.capital * risk_percent
        stop_distance_percent = abs(entry_price - stop_loss_price) / entry_price
        
        if stop_distance_percent == 0:
            return PositionSize(0.0, 0.0, risk_percent, 0.0, False, "Stop loss equals entry price")
        
        position_size = risk_amount / stop_distance_percent
        
        # NEW CHECK: Prevent leverage/position size exceeding total capital
        if position_size > self.capital:
            return PositionSize(
                size=position_size,
                risk_amount=risk_amount,
                risk_percent=risk_percent,
                stop_distance_percent=stop_distance_percent,
                is_valid=False,
                reason=f"Position size R{position_size:.2f} exceeds account capital R{self.capital:.2f}"
            )

        # 3. THE GATEKEEPER: Run through all behavioral and mathematical limits
        is_approved, gate_reason = self.validate_trade(position_size, risk_amount, risk_percent)
        
        # 4. Exchange Minimum Check (Specific to real-world execution)
        if is_approved and position_size < EXCHANGE_MIN_ZAR:
    # If we are within 15% of the minimum, just bump it up to the minimum
            if position_size >= (EXCHANGE_MIN_ZAR * 0.85):
                position_size = EXCHANGE_MIN_ZAR + 1.0 # Force R186
                is_approved = True
                gate_reason = "OK (Forced to Exchange Minimum)"
            else:
                is_approved = False
                gate_reason = f"Position R{position_size:.2f} too far below minimum R{EXCHANGE_MIN_ZAR}"

        return PositionSize(
            size=position_size,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            stop_distance_percent=stop_distance_percent,
            is_valid=is_approved,
            reason=gate_reason
        )

    def validate_trade(
        self,
        position_size: float,
        risk_amount: float,
        risk_percent: float,
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """
        Validate if trade is allowed based on all risk limits.
        
        This is the GATEKEEPER. Every trade must pass through here.
        
        Checks (in order):
        1. Per-trade risk limit
        2. Cooldown period (after consecutive losses)
        3. Daily loss limit
        4. Daily trade limit
        5. Consecutive loss limit
        6. Kill switch status
        
        Args:
            position_size: Calculated position size
            risk_amount: Amount of capital at risk
            risk_percent: Risk as percentage of capital
            
        Returns:
            (is_approved, reason)
        """
        # Check if date changed (reset daily counters)
        self._check_date_rollover(current_time)
        
        # Gate 1: Per-trade risk limit
        if risk_percent > RISK_LIMITS.MAX_RISK_PER_TRADE:
            return False, f"Risk {risk_percent*100:.2f}% exceeds limit"
        
        # Gate 2: Cooldown period check (NOW ACTIVE)
        if self.state.is_in_cooldown(current_time):
            return False, "Cooldown period active after loss streak."
        
        # Gate 3: Daily loss limit (NOW ACTIVE)
        max_loss = self.capital * RISK_LIMITS.MAX_DAILY_LOSS
        if self.state.daily_loss >= max_loss:
            return False, f"Daily loss limit reached (R{self.state.daily_loss:.2f})"
        
        # Gate 4: Daily trade limit (NOW ACTIVE)
        if self.state.trades_today >= RISK_LIMITS.MAX_TRADES_PER_DAY:
            return False, f"Max daily trades ({RISK_LIMITS.MAX_TRADES_PER_DAY}) reached."
        
        # Gate 5: Consecutive loss limit (NOW ACTIVE)
        if self.state.consecutive_losses >= RISK_LIMITS.MAX_CONSECUTIVE_LOSSES:
            return False, f"Stopped: {self.state.consecutive_losses} consecutive losses."
        
        # Gate 6: Kill switch (NOW ACTIVE)
        if self.state.kill_switch_active:
            return False, f"Kill switch ACTIVE: {self.state.kill_switch_reason}"
        
        # Additional sanity checks
        if position_size <= 0:
            return False, "Position size must be positive"
        
        if risk_amount > self.capital:
            return False, "Risk amount exceeds total capital"
        
        # All gates passed
        return True, "Trade approved"

    def _check_date_rollover(self, current_time: Optional[datetime] = None) -> None:
        """Check if date changed and reset daily counters."""
        # Use provided time if available (backtesting), otherwise system time
        effective_date = current_time.date() if current_time else datetime.now().date()
        
        if effective_date != self.state.current_date:
            logger.info(f"Date rollover: {self.state.current_date} → {effective_date}. Resetting.")
            self.state.reset_daily()
            self.state.current_date = effective_date

    def _validate_inputs(self, entry: float, stop: float, risk: float) -> Tuple[bool, str]:
        if entry <= 0 or stop <= 0:
            return False, "Prices must be positive"
        
        stop_pct = abs(entry - stop) / entry
        if stop_pct < 0.001:
            return False, f"Stop loss too tight: {stop_pct*100:.3f}%"
        if stop_pct > 0.20:
            return False, f"Stop loss too wide: {stop_pct*100:.1f}%"
            
        return True, "OK"

    def record_trade(
        self,
        pnl: float,
        risk_amount: float,
        current_time: Optional[datetime] = None
    ) -> None:
        """
        Record trade outcome and update state.
        
        This MUST be called after every trade to maintain accurate state.
        
        Args:
            pnl: Profit/loss of the trade (negative for loss)
            risk_amount: Amount that was at risk
        """
        self.state.trades_today += 1
        
        # Update capital
        new_capital = self.capital + pnl
        self.update_capital(new_capital)
        
        # Track losses
        if pnl < 0:
            self.state.daily_loss += abs(pnl)
            self.state.consecutive_losses += 1
            self.state.last_trade_result = 'loss'
            
            logger.warning(
                f"Loss recorded: R{pnl:.2f}. "
                f"Consecutive losses: {self.state.consecutive_losses}"
            )
            
            # Activate cooldown if hit consecutive loss limit
            if self.state.consecutive_losses >= RISK_LIMITS.MAX_CONSECUTIVE_LOSSES:
                base_time = current_time if current_time else datetime.now()
                self.state.cooldown_until = base_time + timedelta(hours=RISK_LIMITS.LOSS_STREAK_COOLDOWN_HOURS)
                logger.critical(
                    f"⚠️  Consecutive loss limit reached. "
                    f"Cooldown activated for {RISK_LIMITS.LOSS_STREAK_COOLDOWN_HOURS}h"
                )
        else:
            # Win resets consecutive losses and clears cooldown
            self.state.consecutive_losses = 0
            self.state.clear_cooldown()
            self.state.last_trade_result = 'win'
            
            logger.info(f"Win recorded: R{pnl:.2f}")

    def update_capital(self, new_capital: float) -> None:
        """
        Update current capital and check drawdown.
        
        Args:
            new_capital: New capital amount
            
        Raises:
            ValueError: If new capital is invalid
        """
        if new_capital <= 0:
            raise ValueError(f"Capital must be positive, got {new_capital}")
        
        # Update capital tracker (checks for kill switch)
        kill_switch_triggered, reason = self.capital_tracker.update(new_capital)
        
        # If kill switch triggered, activate it
        if kill_switch_triggered:
            self.activate_kill_switch(reason)
        
        logger.info(f"Capital updated: {self.capital} → {new_capital}")
        self.capital = new_capital

    def activate_kill_switch(self, reason: str) -> None:
        self.state.kill_switch_active = True
        self.state.kill_switch_reason = reason
        logger.critical(f"🚨 KILL SWITCH ACTIVATED: {reason}")

    def deactivate_kill_switch(self) -> None:
        self.state.kill_switch_active = False
        self.state.kill_switch_reason = ""
        logger.warning("Kill switch deactivated.")

    def reset_consecutive_losses(self) -> None:
        self.state.consecutive_losses = 0
        logger.info("Consecutive losses reset.")

    def get_capital_stats(self) -> dict:
        """
        Get comprehensive capital statistics.
        
        Returns:
            Dictionary with capital metrics
        """
        return self.capital_tracker.get_statistics()
    
    def get_drawdown(self) -> float:
        """
        Get current drawdown percentage.
        
        Returns:
            Drawdown as decimal (e.g., 0.05 = 5%)
        """
        return self.capital_tracker.get_drawdown()
    
    def get_status(self) -> dict:
        """
        Get comprehensive risk engine status.
        
        Returns:
            Dictionary with all risk metrics and limits
        """
        capital_stats = self.capital_tracker.get_statistics()
        
        status = {
            # Capital
            'capital': {
                'current': self.capital,
                'peak': capital_stats['peak'],
                'starting': capital_stats['starting'],
                'drawdown_pct': capital_stats['drawdown_pct'],
                'total_return_pct': capital_stats['total_return_pct'],
            },
            
            # Daily limits
            'daily': {
                'trades_today': self.state.trades_today,
                'max_trades': RISK_LIMITS.MAX_TRADES_PER_DAY,
                'trades_remaining': max(0, RISK_LIMITS.MAX_TRADES_PER_DAY - self.state.trades_today),
                'loss_today': self.state.daily_loss,
                'max_daily_loss': self.capital * RISK_LIMITS.MAX_DAILY_LOSS,
                'loss_remaining': max(0, self.capital * RISK_LIMITS.MAX_DAILY_LOSS - self.state.daily_loss),
            },
            
            # Consecutive losses
            'streak': {
                'consecutive_losses': self.state.consecutive_losses,
                'max_allowed': RISK_LIMITS.MAX_CONSECUTIVE_LOSSES,
                'last_result': self.state.last_trade_result,
                'in_cooldown': self.state.is_in_cooldown(),
                'cooldown_until': self.state.cooldown_until.isoformat() if self.state.cooldown_until else None,
            },
            
            # Kill switch
            'kill_switch': {
                'active': self.state.kill_switch_active,
                'reason': self.state.kill_switch_reason,
                'drawdown_threshold': RISK_LIMITS.MAX_DRAWDOWN_FROM_PEAK * 100,
            },
            
            # Trading permission
            'can_trade': self._can_trade_now(),
        }
        
        return status
    
    def _can_trade_now(self) -> bool:
        """
        Quick check if trading is currently allowed.
        
        Returns:
            True if can trade, False otherwise
        """
        # Use a minimal validation check
        is_valid, _ = self.validate_trade(
            position_size=10,  # Dummy value
            risk_amount=0.1,   # Dummy value
            risk_percent=RISK_LIMITS.MIN_RISK_PER_TRADE
        )
        
        return is_valid
    
    def print_status(self) -> None:
        """Print formatted risk engine status."""
        status = self.get_status()
        
        print("=" * 60)
        print("RISK ENGINE STATUS")
        print("=" * 60)
        
        # Capital
        print("\n💰 CAPITAL")
        print(f"   Current: R{status['capital']['current']:.2f}")
        print(f"   Peak: R{status['capital']['peak']:.2f}")
        print(f"   Drawdown: {status['capital']['drawdown_pct']:.2f}%")
        print(f"   Total Return: {status['capital']['total_return_pct']:+.2f}%")
        
        # Daily limits
        print("\n📅 DAILY LIMITS")
        print(f"   Trades: {status['daily']['trades_today']} / {status['daily']['max_trades']}")
        print(f"   Loss: R{status['daily']['loss_today']:.2f} / R{status['daily']['max_daily_loss']:.2f}")
        
        # Streak
        print("\n📊 CONSECUTIVE LOSSES")
        print(f"   Current streak: {status['streak']['consecutive_losses']}")
        print(f"   Max allowed: {status['streak']['max_allowed']}")
        print(f"   Last result: {status['streak']['last_result'] or 'None'}")
        
        if status['streak']['in_cooldown']:
            print(f"   ⚠️  COOLDOWN ACTIVE until {status['streak']['cooldown_until']}")
        
        # Kill switch
        print("\n🚨 KILL SWITCH")
        if status['kill_switch']['active']:
            print(f"   ❌ ACTIVE: {status['kill_switch']['reason']}")
        else:
            print(f"   ✅ Inactive")
        print(f"   Threshold: {status['kill_switch']['drawdown_threshold']:.1f}% drawdown")
        
        # Overall
        print("\n" + "=" * 60)
        if status['can_trade']:
            print("✅ TRADING ALLOWED")
        else:
            print("❌ TRADING BLOCKED")
        print("=" * 60)


def main():
    """Test complete risk engine."""
    print("=" * 60)
    print("COMPLETE RISK ENGINE TEST")
    print("=" * 60)
    
    engine = RiskEngine(capital=500)
    
    # Show initial status
    print("\n📊 Initial Status:")
    engine.print_status()
    
    # Simulate trades
    print("\n" + "=" * 60)
    print("SIMULATING TRADES")
    print("=" * 60)
    
    # Trade 1: Win
    print("\n1. Trade 1 (Win)")
    pos = engine.calculate_position_size(42000, 41160, 0.005)
    valid, reason = engine.validate_trade(pos.size, pos.risk_amount, pos.risk_percent)
    print(f"   Valid: {valid}")
    if valid:
        engine.record_trade(pnl=3.0, risk_amount=2.5)
        print(f"   Capital: R{engine.capital:.2f}")
    
    # Trade 2: Loss
    print("\n2. Trade 2 (Loss)")
    pos = engine.calculate_position_size(42000, 41160, 0.005)
    valid, reason = engine.validate_trade(pos.size, pos.risk_amount, pos.risk_percent)
    if valid:
        engine.record_trade(pnl=-2.5, risk_amount=2.5)
        print(f"   Capital: R{engine.capital:.2f}")
        print(f"   Consecutive losses: {engine.state.consecutive_losses}")
    
    # Trade 3: Another loss (triggers cooldown)
    print("\n3. Trade 3 (Loss - triggers cooldown)")
    pos = engine.calculate_position_size(42000, 41160, 0.005)
    valid, reason = engine.validate_trade(pos.size, pos.risk_amount, pos.risk_percent)
    if valid:
        engine.record_trade(pnl=-2.5, risk_amount=2.5)
        print(f"   Cooldown active: {engine.state.is_in_cooldown()}")
    
    # Try trade 4 (should be rejected)
    print("\n4. Trade 4 (Should be rejected)")
    pos = engine.calculate_position_size(42000, 41160, 0.005)
    valid, reason = engine.validate_trade(pos.size, pos.risk_amount, pos.risk_percent)
    print(f"   Valid: {valid}")
    print(f"   Reason: {reason}")
    
    # Final status
    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)
    engine.print_status()


if __name__ == "__main__":
    main()   
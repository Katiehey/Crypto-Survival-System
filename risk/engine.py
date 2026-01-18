"""
Risk Engine - Capital Preservation System

The risk engine is the guardian of capital. It calculates position sizes,
validates trades against risk limits, and enforces safety constraints.

This is THE most critical component of the system. Every calculation
must be mathematically correct. No shortcuts.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Tuple, Optional

from config.system_config import RISK_LIMITS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# EXCHANGE_MIN_ZAR: Approx $10 minimum notional requirement for most exchanges
# This prevents the bot from attempting orders that will be rejected.
EXCHANGE_MIN_ZAR = 185.0

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
    kill_switch_active: bool = False
    kill_switch_reason: str = ""

    def reset_daily(self) -> None:
        """Reset daily counters (called at midnight)."""
        self.current_date = datetime.now().date()
        self.trades_today = 0
        self.daily_loss = 0.0


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
        if capital <= 0:
            raise ValueError(f"Capital must be positive, got {capital}")
        
        self.capital = capital
        self.state = TradeState()
        logger.info(f"RiskEngine initialized with capital: R{capital:.2f}")

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        risk_percent: Optional[float] = None
    ) -> PositionSize:
        """Calculate position size and validate against all risk limits."""
        
        # Use default risk if not specified
        if risk_percent is None:
            risk_percent = RISK_LIMITS.MAX_RISK_PER_TRADE
        
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
        
        # 3. THE GATEKEEPER: Run through all behavioral and mathematical limits
        is_approved, gate_reason = self.validate_trade(position_size, risk_amount, risk_percent)
        
        # 4. Exchange Minimum Check (Specific to real-world execution)
        if is_approved and position_size < EXCHANGE_MIN_ZAR:
            is_approved = False
            gate_reason = f"Position R{position_size:.2f} below exchange minimum R{EXCHANGE_MIN_ZAR}"

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
        risk_percent: float
    ) -> Tuple[bool, str]:
        """
        Validate if trade is allowed based on all risk limits.
        This is the GATEKEEPER. Every trade must pass through here.
        """
        self._check_date_rollover()
        
        # GATE 1: KILL SWITCH (Check this first - it's a hard stop)
        if self.state.kill_switch_active:
            return False, f"Kill switch ACTIVE: {self.state.kill_switch_reason}"

        # GATE 2: CONSECUTIVE LOSS LIMIT (Behavioral signal)
        # We check this early so the test finds "consecutive loss" in the reason.
        if self.state.consecutive_losses >= RISK_LIMITS.MAX_CONSECUTIVE_LOSSES:
            return False, (
                f"Consecutive loss limit reached: {self.state.consecutive_losses} losses. "
                "Cooldown period active."
            )

        # GATE 3: PER-TRADE RISK LIMIT
        if risk_percent > RISK_LIMITS.MAX_RISK_PER_TRADE:
            return False, (
                f"Risk {risk_percent*100:.2f}% exceeds per-trade limit "
                f"{RISK_LIMITS.MAX_RISK_PER_TRADE*100:.2f}%"
            )
        
        # GATE 4: DAILY LOSS LIMIT
        max_daily_loss = self.capital * RISK_LIMITS.MAX_DAILY_LOSS
        if self.state.daily_loss >= max_daily_loss:
            return False, (
                f"Daily loss limit reached: "
                f"R{self.state.daily_loss:.2f} / R{max_daily_loss:.2f}"
            )
        
        # GATE 5: DAILY TRADE LIMIT
        if self.state.trades_today >= RISK_LIMITS.MAX_TRADES_PER_DAY:
            return False, (
                f"Daily trade limit reached: "
                f"{self.state.trades_today} / {RISK_LIMITS.MAX_TRADES_PER_DAY}"
            )
        
        # GATE 6: POSITION SIZE CAP
        max_pos_size = self.capital * RISK_LIMITS.MAX_POSITION_SIZE_PERCENT
        if position_size > max_pos_size:
            return False, (f"Position R{position_size:.2f} exceeds cap R{max_pos_size:.2f} "
                           f"({RISK_LIMITS.MAX_POSITION_SIZE_PERCENT*100:.1f}%)")
        
        # SANITY CHECKS
        if position_size <= 0:
            return False, "Position size must be positive"
        
        if risk_amount > self.capital:
            return False, "Risk amount exceeds total capital"
        
        return True, "Trade approved"

    def _check_date_rollover(self) -> None:
        """Check if date changed and reset daily counters."""
        current_date = datetime.now().date()
        if current_date != self.state.current_date:
            logger.info(f"Date rollover: {self.state.current_date} → {current_date}. Resetting counters.")
            self.state.reset_daily()

    def _validate_inputs(self, entry: float, stop: float, risk: float) -> Tuple[bool, str]:
        if entry <= 0 or stop <= 0:
            return False, "Prices must be positive"
        
        stop_pct = abs(entry - stop) / entry
        if stop_pct < 0.001:
            return False, f"Stop loss too tight: {stop_pct*100:.3f}%"
        if stop_pct > 0.20:
            return False, f"Stop loss too wide: {stop_pct*100:.1f}%"
            
        return True, "OK"

    def report_trade_result(self, result: str, loss_amount: float = 0.0):
        """Update state after a trade completes. Triggers Kill Switch if breached."""
        self.state.trades_today += 1
        
        if result == 'loss':
            self.state.daily_loss += loss_amount
            self.state.consecutive_losses += 1
            if self.state.consecutive_losses >= RISK_LIMITS.MAX_CONSECUTIVE_LOSSES:
                self.state.kill_switch_active = True
                self.state.kill_switch_reason = f"Max consecutive losses ({self.state.consecutive_losses})"
        else:
            self.state.consecutive_losses = 0
            
        if self.state.daily_loss >= (self.capital * RISK_LIMITS.MAX_DAILY_LOSS):
            self.state.kill_switch_active = True
            self.state.kill_switch_reason = "Max daily loss reached"

    def record_trade(
        self,
        pnl: float,
        risk_amount: float
    ) -> None:
        """
        Record trade outcome and update state.
        
        This MUST be called after every trade to maintain accurate state.
        
        Args:
            pnl: Profit/loss of the trade (negative for loss)
            risk_amount: Amount that was at risk
            
        Example:
            >>> engine.record_trade(pnl=-2.5, risk_amount=2.5)
            # Loss recorded, consecutive losses incremented
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
        else:
            # Win resets consecutive losses
            self.state.consecutive_losses = 0
            self.state.last_trade_result = 'win'
            
            logger.info(f"Win recorded: R{pnl:.2f}")
        
        # Check if cooldown needed
        if self.state.consecutive_losses >= RISK_LIMITS.MAX_CONSECUTIVE_LOSSES:
            logger.warning(
                f"⚠️  Consecutive loss limit reached. "
                f"Cooldown period active until reset."
            )
    
    def reset_consecutive_losses(self) -> None:
        """
        Manually reset consecutive loss counter.
        
        Should only be called after cooldown period (24h) and review.
        """
        old_count = self.state.consecutive_losses
        self.state.consecutive_losses = 0
        
        logger.info(
            f"Consecutive losses reset: {old_count} → 0. "
            f"Trading can resume."
        )
    
    def activate_kill_switch(self, reason: str) -> None:
        """
        Activate kill switch (emergency stop).
        
        Once activated, ALL trades are blocked until manually cleared.
        
        Args:
            reason: Reason for activation
        """
        self.state.kill_switch_active = True
        self.state.kill_switch_reason = reason
        
        logger.critical(
            f"🚨 KILL SWITCH ACTIVATED: {reason}"
        )
    
    def deactivate_kill_switch(self) -> None:
        """
        Deactivate kill switch.
        
        Should only be done after:
        1. Problem resolved
        2. Review completed
        3. Minimum 48h waiting period
        """
        if not self.state.kill_switch_active:
            logger.warning("Kill switch already inactive")
            return
        
        logger.warning(
            f"Kill switch deactivated. Reason was: {self.state.kill_switch_reason}"
        )
        
        self.state.kill_switch_active = False
        self.state.kill_switch_reason = ""

    def update_capital(self, new_capital: float) -> None:
        if new_capital <= 0:
            raise ValueError(f"Capital must be positive, got {new_capital}")
        self.capital = new_capital

    def reset_kill_switch(self):
        self.state.kill_switch_active = False
        self.state.kill_switch_reason = ""
        self.state.consecutive_losses = 0
        self.state.daily_loss = 0.0
        logger.warning("Kill switch manually reset. Trading resumed.")


def main():
    """Test risk validation with scenarios."""
    print("=" * 60)
    print("RISK VALIDATION TEST")
    print("=" * 60)
    
    engine = RiskEngine(capital=500)
    
    # Scenario 1: Normal trade (should pass)
    print("\n1. Normal trade")
    result = engine.calculate_position_size(42000, 41160, 0.005)
    is_valid, reason = engine.validate_trade(
        result.size, result.risk_amount, result.risk_percent
    )
    print(f"   Position: R{result.size:.2f}")
    print(f"   Approved: {is_valid}")
    print(f"   Reason: {reason}")
    
    # Scenario 2: Record a loss, try another trade
    print("\n2. After recording loss")
    engine.record_trade(pnl=-2.5, risk_amount=2.5)
    is_valid, reason = engine.validate_trade(
        result.size, result.risk_amount, result.risk_percent
    )
    print(f"   Consecutive losses: {engine.state.consecutive_losses}")
    print(f"   Approved: {is_valid}")
    print(f"   Reason: {reason}")
    
    # Scenario 3: Record another loss (hits limit)
    print("\n3. After 2nd consecutive loss")
    engine.record_trade(pnl=-2.5, risk_amount=2.5)
    is_valid, reason = engine.validate_trade(
        result.size, result.risk_amount, result.risk_percent
    )
    print(f"   Consecutive losses: {engine.state.consecutive_losses}")
    print(f"   Approved: {is_valid}")
    print(f"   Reason: {reason}")
    
    # Scenario 4: Kill switch
    print("\n4. Kill switch activation")
    engine2 = RiskEngine(capital=500)
    engine2.activate_kill_switch("Test activation")
    is_valid, reason = engine2.validate_trade(
        result.size, result.risk_amount, result.risk_percent
    )
    print(f"   Kill switch active: {engine2.state.kill_switch_active}")
    print(f"   Approved: {is_valid}")
    print(f"   Reason: {reason}")
    
    print("\n" + "=" * 60)
    print("✅ Risk validation test complete")


if __name__ == "__main__":
    main()
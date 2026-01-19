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
from risk.capital_tracker import CapitalTracker

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

    def record_trade(
        self,
        pnl: float,
        risk_amount: float
    ) -> None:
        """Record trade outcome and update state/capital tracker."""
        self.state.trades_today += 1
        
        # Update capital
        new_capital = self.capital + pnl
        self.update_capital(new_capital)
        
        # Sync with capital tracker to monitor drawdowns
        tracker_status = self.capital_tracker.update(new_capital)
        if tracker_status['kill_switch']:
            self.activate_kill_switch(tracker_status['reason'])
        
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
            self.state.consecutive_losses = 0
            self.state.last_trade_result = 'win'
            logger.info(f"Win recorded: R{pnl:.2f}")
        
        if self.state.consecutive_losses >= RISK_LIMITS.MAX_CONSECUTIVE_LOSSES:
            logger.warning("⚠️  Consecutive loss limit reached. Cooldown active.")

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
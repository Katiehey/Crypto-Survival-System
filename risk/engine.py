"""
Risk Engine - Capital Preservation System

The risk engine is the guardian of capital. It calculates position sizes,
validates trades against risk limits, and enforces safety constraints.

This is THE most critical component of the system. Every calculation
must be mathematically correct. No shortcuts.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import logging

from config.system_config import RISK_LIMITS

logger = logging.getLogger(__name__)


@dataclass
class PositionSize:
    """
    Result of position sizing calculation.
    
    Attributes:
        size: Position size in base currency (e.g., USDT)
        risk_amount: Amount of capital at risk
        risk_percent: Risk as percentage of capital
        stop_distance_percent: Stop loss distance as percentage
        is_valid: Whether position passes validation
        reason: Reason if invalid
    """
    size: float
    risk_amount: float
    risk_percent: float
    stop_distance_percent: float
    is_valid: bool
    reason: str = "OK"


class RiskEngine:
    """
    Core risk management engine.
    
    Responsibilities:
    - Calculate position sizes based on risk
    - Validate trades against risk limits
    - Enforce capital preservation rules
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
        logger.info(f"RiskEngine initialized with capital: {capital}")
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        risk_percent: Optional[float] = None
    ) -> PositionSize:
        """
        Calculate position size based on fixed fractional risk.
        
        This uses the "Fixed Fractional" position sizing method:
        1. Determine risk amount (capital × risk %)
        2. Calculate stop distance (entry - stop)
        3. Position size = risk amount / stop distance
        
        Args:
            entry_price: Intended entry price
            stop_loss_price: Stop loss price
            risk_percent: Risk as decimal (e.g., 0.005 = 0.5%)
                         If None, uses RISK_LIMITS.MAX_RISK_PER_TRADE
        
        Returns:
            PositionSize with calculated values and validation
            
        Example:
            >>> engine = RiskEngine(capital=500)
            >>> result = engine.calculate_position_size(
            ...     entry_price=42000,
            ...     stop_loss_price=41160,
            ...     risk_percent=0.005  # 0.5%
            ... )
            >>> result.size
            125.0  # R125 position
            >>> result.risk_amount
            2.5  # R2.50 at risk
        """
        # Use configured risk limit if not specified
        if risk_percent is None:
            risk_percent = RISK_LIMITS.MAX_RISK_PER_TRADE
        
        # Validate inputs
        validation_result = self._validate_inputs(
            entry_price, stop_loss_price, risk_percent
        )
        
        if not validation_result[0]:
            return PositionSize(
                size=0.0,
                risk_amount=0.0,
                risk_percent=risk_percent,
                stop_distance_percent=0.0,
                is_valid=False,
                reason=validation_result[1]
            )
        
        # Calculate risk amount
        risk_amount = self.capital * risk_percent
        
        # Calculate stop distance as percentage
        stop_distance = abs(entry_price - stop_loss_price)
        stop_distance_percent = stop_distance / entry_price
        
        # Prevent division by zero
        if stop_distance_percent == 0:
            return PositionSize(
                size=0.0,
                risk_amount=0.0,
                risk_percent=risk_percent,
                stop_distance_percent=0.0,
                is_valid=False,
                reason="Stop loss equals entry price (zero distance)"
            )
        
        # Calculate position size
        position_size = risk_amount / stop_distance_percent
        
        # Additional validations
        validation = self._validate_position_size(
            position_size, risk_amount, risk_percent
        )
        
        return PositionSize(
            size=position_size,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            stop_distance_percent=stop_distance_percent,
            is_valid=validation[0],
            reason=validation[1]
        )
    
    def _validate_inputs(
        self,
        entry_price: float,
        stop_loss_price: float,
        risk_percent: float
    ) -> Tuple[bool, str]:
        """
        Validate position sizing inputs.
        
        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            risk_percent: Risk percentage
            
        Returns:
            (is_valid, reason)
        """
        # Check for negative or zero values
        if entry_price <= 0:
            return False, f"Entry price must be positive, got {entry_price}"
        
        if stop_loss_price <= 0:
            return False, f"Stop loss price must be positive, got {stop_loss_price}"
        
        if risk_percent <= 0:
            return False, f"Risk percent must be positive, got {risk_percent}"
        
        # Check risk percent is within limits
        if risk_percent > RISK_LIMITS.MAX_RISK_PER_TRADE:
            return False, (
                f"Risk percent {risk_percent*100:.2f}% exceeds maximum "
                f"{RISK_LIMITS.MAX_RISK_PER_TRADE*100:.2f}%"
            )
        
        if risk_percent < RISK_LIMITS.MIN_RISK_PER_TRADE:
            return False, (
                f"Risk percent {risk_percent*100:.2f}% below minimum "
                f"{RISK_LIMITS.MIN_RISK_PER_TRADE*100:.2f}%"
            )
        
        # Check stop loss makes sense (not too far from entry)
        stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price
        
        if stop_distance_pct > 0.20:  # 20% stop is very wide
            return False, f"Stop loss too wide: {stop_distance_pct*100:.1f}%"
        
        if stop_distance_pct < 0.001:  # 0.1% stop is too tight
            return False, f"Stop loss too tight: {stop_distance_pct*100:.3f}%"
        
        return True, "OK"
    
    def _validate_position_size(
        self,
        position_size: float,
        risk_amount: float,
        risk_percent: float
    ) -> Tuple[bool, str]:
        """
        Validate calculated position size.
        
        Args:
            position_size: Calculated position size
            risk_amount: Risk amount in currency
            risk_percent: Risk as percentage
            
        Returns:
            (is_valid, reason)
        """
        # Position size should not exceed max position size limit
        max_position_size = self.capital * RISK_LIMITS.MAX_POSITION_SIZE_PERCENT
        
        if position_size > max_position_size:
            return False, (
                f"Position size {position_size:.2f} exceeds maximum "
                f"{max_position_size:.2f} "
                f"({RISK_LIMITS.MAX_POSITION_SIZE_PERCENT*100:.1f}% of capital)"
            )
        
        # Position size should be meaningful (not too small)
        min_position_size = 10.0  # Minimum R10 position to be meaningful
        
        if position_size < min_position_size:
            return False, (
                f"Position size {position_size:.2f} too small "
                f"(minimum {min_position_size})"
            )
        
        # Risk amount sanity check
        if risk_amount > self.capital * 0.01:  # Should never risk >1%
            return False, (
                f"Risk amount {risk_amount:.2f} exceeds 1% of capital "
                f"({self.capital * 0.01:.2f})"
            )
        
        return True, "OK"
    
    def update_capital(self, new_capital: float) -> None:
        """
        Update current capital.
        
        Args:
            new_capital: New capital amount
            
        Raises:
            ValueError: If new capital is invalid
        """
        if new_capital <= 0:
            raise ValueError(f"Capital must be positive, got {new_capital}")
        
        logger.info(f"Capital updated: {self.capital} → {new_capital}")
        self.capital = new_capital


def main():
    """Test position sizing with examples."""
    print("=" * 60)
    print("POSITION SIZING TEST")
    print("=" * 60)
    
    engine = RiskEngine(capital=500)
    
    # Test case 1: Normal trade
    print("\n1. Normal trade (2% stop)")
    result = engine.calculate_position_size(
        entry_price=42000,
        stop_loss_price=41160,  # 2% stop
        risk_percent=0.005  # 0.5% risk
    )
    
    print(f"   Entry: R42,000")
    print(f"   Stop: R41,160 (2% below)")
    print(f"   Risk: 0.5% of R500 = R{result.risk_amount:.2f}")
    print(f"   Position size: R{result.size:.2f}")
    print(f"   Valid: {result.is_valid}")
    print(f"   Reason: {result.reason}")
    
    # Verify math
    expected_loss = result.size * result.stop_distance_percent
    print(f"   Verification: R{result.size:.2f} × {result.stop_distance_percent*100:.2f}% = R{expected_loss:.2f}")
    
    # Test case 2: Tight stop
    print("\n2. Tight stop (0.5% stop)")
    result2 = engine.calculate_position_size(
        entry_price=42000,
        stop_loss_price=41790,  # 0.5% stop
        risk_percent=0.005
    )
    
    print(f"   Entry: R42,000")
    print(f"   Stop: R41,790 (0.5% below)")
    print(f"   Position size: R{result2.size:.2f}")
    print(f"   Valid: {result2.is_valid}")
    
    # Test case 3: Wide stop
    print("\n3. Wide stop (5% stop)")
    result3 = engine.calculate_position_size(
        entry_price=42000,
        stop_loss_price=39900,  # 5% stop
        risk_percent=0.005
    )
    
    print(f"   Entry: R42,000")
    print(f"   Stop: R39,900 (5% below)")
    print(f"   Position size: R{result3.size:.2f}")
    print(f"   Valid: {result3.is_valid}")
    print(f"   Reason: {result3.reason}")
    
    print("\n" + "=" * 60)
    print("✅ Position sizing test complete")


if __name__ == "__main__":
    main()
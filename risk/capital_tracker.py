"""
Capital Tracker - Monitors capital and drawdown.

This module tracks:
- Current capital
- Peak capital (highest point reached)
- Drawdown percentage
- Kill switch triggers based on drawdown
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from datetime import datetime
import logging

from config.system_config import RISK_LIMITS

logger = logging.getLogger(__name__)


@dataclass
class CapitalSnapshot:
    """
    Snapshot of capital state at a point in time.
    
    Attributes:
        timestamp: When snapshot was taken
        current: Current capital
        peak: Peak capital reached
        drawdown_pct: Drawdown as percentage (0-1)
    """
    timestamp: datetime
    current: float
    peak: float
    drawdown_pct: float


class CapitalTracker:
    """
    Tracks capital and monitors for dangerous drawdowns.
    
    Responsibilities:
    - Track current capital
    - Track peak capital (all-time high)
    - Calculate drawdown from peak
    - Trigger kill switch on excessive drawdown
    """
    
    def __init__(self, starting_capital: float):
        """
        Initialize capital tracker.
        
        Args:
            starting_capital: Initial capital amount
            
        Raises:
            ValueError: If starting capital is invalid
        """
        if starting_capital <= 0:
            raise ValueError(f"Starting capital must be positive, got {starting_capital}")
        
        self.current = starting_capital
        self.peak = starting_capital
        self.starting = starting_capital
        
        # History tracking
        self.history: list[CapitalSnapshot] = []
        self._record_snapshot()
        
        logger.info(f"CapitalTracker initialized with R{starting_capital:.2f}")
    
    def update(self, new_capital: float) -> Tuple[bool, str]:
        """
        Update capital and check for kill switch trigger.
        
        Args:
            new_capital: New capital amount
            
        Returns:
            (kill_switch_triggered, reason)
            
        Example:
            >>> tracker = CapitalTracker(500)
            >>> tracker.update(485)  # Lost R15
            >>> tracker.get_drawdown()
            0.03  # 3% drawdown
        """
        if new_capital <= 0:
            logger.critical(f"Capital dropped to {new_capital} (zero or negative!)")
            return True, "Capital depleted to zero or negative"
        
        old_capital = self.current
        self.current = new_capital
        
        # Update peak if new high
        if new_capital > self.peak:
            logger.info(f"New peak capital: R{self.peak:.2f} → R{new_capital:.2f}")
            self.peak = new_capital
        
        # Record snapshot
        self._record_snapshot()
        
        # Check for kill switch trigger
        drawdown = self.get_drawdown()
        
        if drawdown >= RISK_LIMITS.MAX_DRAWDOWN_FROM_PEAK:
            reason = (
                f"Drawdown {drawdown*100:.2f}% exceeds maximum "
                f"{RISK_LIMITS.MAX_DRAWDOWN_FROM_PEAK*100:.1f}%. "
                f"Peak: R{self.peak:.2f}, Current: R{self.current:.2f}"
            )
            logger.critical(f"🚨 KILL SWITCH TRIGGERED: {reason}")
            return True, reason
        
        # Log significant changes
        pct_change = (new_capital - old_capital) / old_capital
        if abs(pct_change) > 0.01:  # >1% change
            direction = "↑" if pct_change > 0 else "↓"
            logger.info(
                f"Capital {direction}: R{old_capital:.2f} → R{new_capital:.2f} "
                f"({pct_change*100:+.2f}%)"
            )
        
        return False, "OK"
    
    def get_drawdown(self) -> float:
        """
        Calculate current drawdown from peak.
        
        Returns:
            Drawdown as decimal (e.g., 0.05 = 5%)
        """
        if self.peak == 0:
            return 0.0
        
        drawdown = (self.peak - self.current) / self.peak
        return max(0.0, drawdown)  # Ensure non-negative
    
    def get_drawdown_amount(self) -> float:
        """
        Get drawdown in currency units.
        
        Returns:
            Amount of capital lost from peak
        """
        return self.peak - self.current
    
    def get_return_from_start(self) -> float:
        """
        Calculate total return from starting capital.
        
        Returns:
            Return as decimal (e.g., 0.10 = 10% gain)
        """
        if self.starting == 0:
            return 0.0
        
        return (self.current - self.starting) / self.starting
    
    def get_peak_return(self) -> float:
        """
        Calculate peak return (best performance achieved).
        
        Returns:
            Peak return as decimal
        """
        if self.starting == 0:
            return 0.0
        
        return (self.peak - self.starting) / self.starting
    
    def is_at_peak(self) -> bool:
        """Check if currently at peak capital."""
        return abs(self.current - self.peak) < 0.01  # Within 1 cent
    
    def _record_snapshot(self) -> None:
        """Record current state in history."""
        snapshot = CapitalSnapshot(
            timestamp=datetime.now(),
            current=self.current,
            peak=self.peak,
            drawdown_pct=self.get_drawdown()
        )
        
        self.history.append(snapshot)
        
        # Keep last 1000 snapshots max
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
    
    def get_statistics(self) -> dict:
        """
        Get comprehensive capital statistics.
        
        Returns:
            Dictionary with all capital metrics
        """
        return {
            'current': self.current,
            'peak': self.peak,
            'starting': self.starting,
            'drawdown_pct': self.get_drawdown() * 100,
            'drawdown_amount': self.get_drawdown_amount(),
            'total_return_pct': self.get_return_from_start() * 100,
            'peak_return_pct': self.get_peak_return() * 100,
            'at_peak': self.is_at_peak(),
            'kill_switch_threshold': RISK_LIMITS.MAX_DRAWDOWN_FROM_PEAK * 100,
        }


def main():
    """Test capital tracker with scenarios."""
    print("=" * 60)
    print("CAPITAL TRACKER TEST")
    print("=" * 60)
    
    tracker = CapitalTracker(starting_capital=500)
    
    # Scenario 1: Initial state
    print("\n1. Initial state")
    stats = tracker.get_statistics()
    print(f"   Current: R{stats['current']:.2f}")
    print(f"   Peak: R{stats['peak']:.2f}")
    print(f"   Drawdown: {stats['drawdown_pct']:.2f}%")
    
    # Scenario 2: Make profit (new peak)
    print("\n2. After profit (new peak)")
    tracker.update(510)
    stats = tracker.get_statistics()
    print(f"   Current: R{stats['current']:.2f}")
    print(f"   Peak: R{stats['peak']:.2f}")
    print(f"   Total return: {stats['total_return_pct']:+.2f}%")
    
    # Scenario 3: Small drawdown
    print("\n3. After small loss")
    tracker.update(500)
    stats = tracker.get_statistics()
    print(f"   Current: R{stats['current']:.2f}")
    print(f"   Peak: R{stats['peak']:.2f}")
    print(f"   Drawdown: {stats['drawdown_pct']:.2f}%")
    
    # Scenario 4: Approach kill switch threshold
    print("\n4. Approaching kill switch (4.5% drawdown)")
    tracker.update(487)  # 4.5% from peak
    stats = tracker.get_statistics()
    kill_switch, reason = tracker.update(487)
    print(f"   Current: R{stats['current']:.2f}")
    print(f"   Peak: R{stats['peak']:.2f}")
    print(f"   Drawdown: {stats['drawdown_pct']:.2f}%")
    print(f"   Kill switch: {kill_switch}")
    
    # Scenario 5: Trigger kill switch
    print("\n5. Trigger kill switch (5.1% drawdown)")
    kill_switch, reason = tracker.update(484)  # 5.1% from peak
    stats = tracker.get_statistics()
    print(f"   Current: R{stats['current']:.2f}")
    print(f"   Drawdown: {stats['drawdown_pct']:.2f}%")
    print(f"   Kill switch: {kill_switch}")
    print(f"   Reason: {reason}")
    
    print("\n" + "=" * 60)
    print("✅ Capital tracker test complete")


if __name__ == "__main__":
    main()
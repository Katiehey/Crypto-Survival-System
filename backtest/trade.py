"""
Trade record for backtesting.

Represents a completed historical trade with all details.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Trade:
    """
    Record of a completed trade in backtest.
    
    Attributes:
        trade_id: Unique identifier
        entry_time: When position was opened
        entry_price: Price at entry
        entry_regime: Market regime at entry
        exit_time: When position was closed
        exit_price: Price at exit
        exit_regime: Market regime at exit
        exit_reason: Why position was closed
        size: Position size (in quote currency)
        side: 'long' or 'short'
        pnl: Profit/loss in quote currency
        pnl_percent: Profit/loss as percentage
        fees_paid: Total fees (entry + exit)
        max_favorable_excursion: Best price reached (MFE)
        max_adverse_excursion: Worst price reached (MAE)
    """
    
    trade_id: str
    
    # Entry
    entry_time: datetime
    entry_price: float
    entry_regime: str
    
    # Exit
    exit_time: datetime
    exit_price: float
    exit_regime: str
    exit_reason: str  # 'stop_loss', 'strategy_exit', 'end_of_data'
    
    # Position
    size: float
    side: str  # 'long' or 'short'
    
    # Performance
    pnl: float
    pnl_percent: float
    fees_paid: float
    
    # Excursion tracking
    max_favorable_excursion: float = 0.0  # MFE
    max_adverse_excursion: float = 0.0    # MAE
    
    def __post_init__(self):
        """Validate trade data."""
        if self.side not in ['long', 'short']:
            raise ValueError(f"Side must be 'long' or 'short', got {self.side}")
        
        if self.size <= 0:
            raise ValueError(f"Size must be positive, got {self.size}")
        
        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError("Prices must be positive")
        
        if self.exit_time < self.entry_time:
            raise ValueError("Exit time must be after entry time")
    
    @property
    def duration(self) -> float:
        """Trade duration in hours."""
        delta = self.exit_time - self.entry_time
        return delta.total_seconds() / 3600
    
    @property
    def is_winner(self) -> bool:
        """Check if trade was profitable."""
        return self.pnl > 0
    
    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """
        Calculate risk/reward ratio.
        
        Returns:
            Ratio of profit to risk, or None if MAE is zero
        """
        if self.max_adverse_excursion == 0:
            return None
        
        return self.max_favorable_excursion / self.max_adverse_excursion
    
    def to_dict(self) -> dict:
        """Convert to dictionary for export."""
        return {
            'trade_id': self.trade_id,
            'entry_time': self.entry_time.isoformat(),
            'entry_price': self.entry_price,
            'entry_regime': self.entry_regime,
            'exit_time': self.exit_time.isoformat(),
            'exit_price': self.exit_price,
            'exit_regime': self.exit_regime,
            'exit_reason': self.exit_reason,
            'size': self.size,
            'side': self.side,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'fees_paid': self.fees_paid,
            'duration_hours': self.duration,
            'is_winner': self.is_winner,
            'mfe': self.max_favorable_excursion,
            'mae': self.max_adverse_excursion,
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Trade({self.trade_id}: {self.side} "
            f"${self.size:.2f} @ ${self.entry_price:.2f} → ${self.exit_price:.2f}, "
            f"PnL: ${self.pnl:+.2f} ({self.pnl_percent:+.2f}%), "
            f"{self.exit_reason})"
        )


def create_trade(
    trade_id: str,
    entry_time: datetime,
    entry_price: float,
    entry_regime: str,
    exit_time: datetime,
    exit_price: float,
    exit_regime: str,
    exit_reason: str,
    size: float,
    side: str = 'long',
    fee_rate: float = 0.00075
) -> Trade:
    """
    Create a trade with automatic PnL calculation.
    
    Args:
        trade_id: Unique identifier
        entry_time: Entry timestamp
        entry_price: Entry price
        entry_regime: Regime at entry
        exit_time: Exit timestamp
        exit_price: Exit price
        exit_regime: Regime at exit
        exit_reason: Reason for exit
        size: Position size (quote currency)
        side: 'long' or 'short'
        fee_rate: Fee rate for calculations
        
    Returns:
        Complete Trade object with calculated PnL
    """
    # Calculate fees
    entry_fee = size * fee_rate
    exit_fee = size * fee_rate
    total_fees = entry_fee + exit_fee
    
    # Calculate PnL (assuming long only for now)
    if side == 'long':
        price_change = exit_price - entry_price
        price_change_pct = price_change / entry_price
        
        # PnL in quote currency
        pnl = (size / entry_price) * price_change - total_fees
        pnl_percent = (pnl / size) * 100
    else:
        # Short not implemented yet
        raise NotImplementedError("Short positions not yet supported")
    
    return Trade(
        trade_id=trade_id,
        entry_time=entry_time,
        entry_price=entry_price,
        entry_regime=entry_regime,
        exit_time=exit_time,
        exit_price=exit_price,
        exit_regime=exit_regime,
        exit_reason=exit_reason,
        size=size,
        side=side,
        pnl=pnl,
        pnl_percent=pnl_percent,
        fees_paid=total_fees
    )


def main():
    """Test trade creation."""
    print("=" * 60)
    print("TRADE CLASS TEST")
    print("=" * 60)
    
    # Create sample trade
    trade = create_trade(
        trade_id="TEST_001",
        entry_time=datetime(2024, 1, 1, 10, 0),
        entry_price=42000,
        entry_regime='trend',
        exit_time=datetime(2024, 1, 1, 14, 0),
        exit_price=42500,
        exit_regime='trend',
        exit_reason='strategy_exit',
        size=250,  # R250 position
        side='long'
    )
    
    print(f"\n{trade}")
    print(f"\nDuration: {trade.duration:.1f} hours")
    print(f"Winner: {trade.is_winner}")
    print(f"\nTrade dict:")
    for key, value in trade.to_dict().items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("✅ Trade class test complete")


if __name__ == "__main__":
    main()
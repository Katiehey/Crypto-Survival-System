"""
Equity curve generation and analysis for backtesting.

Tracks capital evolution over time and provides:
- Complete equity time series
- Peak equity tracking
- Drawdown periods identification
- Return calculation by period
- Visual representation helpers
"""

from typing import List, Tuple, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from backtest.trade import Trade


class EquityCurve:
    """
    Generate and analyze equity curve from backtest results.
    
    Tracks capital evolution through time, identifies peaks and drawdowns,
    and provides various metrics for performance analysis.
    """
    
    def __init__(self, initial_capital: float):
        """
        Initialize equity curve tracker.
        
        Args:
            initial_capital: Starting capital amount
        """
        self.initial_capital = initial_capital
        self.data: List[dict] = []
        
        # Add initial point
        self._add_point(
            timestamp=datetime.now(),
            capital=initial_capital,
            trade_id=None,
            trade_pnl=0.0
        )
    
    def _add_point(
        self,
        timestamp: datetime,
        capital: float,
        trade_id: Optional[str],
        trade_pnl: float
    ) -> None:
        """Add equity point to curve."""
        self.data.append({
            'timestamp': timestamp,
            'capital': capital,
            'trade_id': trade_id,
            'trade_pnl': trade_pnl,
        })
    
    def add_trade(self, trade: Trade, capital_after: float) -> None:
        """
        Add trade to equity curve.
        
        Args:
            trade: Completed trade
            capital_after: Capital after trade closes
        """
        self._add_point(
            timestamp=trade.exit_time,
            capital=capital_after,
            trade_id=trade.trade_id,
            trade_pnl=trade.pnl
        )
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert equity curve to DataFrame.
        
        Returns:
            DataFrame with equity curve data
        """
        df = pd.DataFrame(self.data)
        
        if len(df) == 0:
            return df
        
        # Calculate additional metrics
        df['peak'] = df['capital'].expanding().max()
        df['drawdown'] = (df['capital'] - df['peak']) / df['peak']
        df['drawdown_pct'] = df['drawdown'] * 100
        df['return_pct'] = (df['capital'] - self.initial_capital) / self.initial_capital * 100
        
        # Cumulative PnL
        df['cumulative_pnl'] = df['capital'] - self.initial_capital
        
        return df
    
    def get_equity_series(self) -> pd.Series:
        """
        Get equity as pandas Series.
        
        Returns:
            Series indexed by timestamp with capital values
        """
        df = self.to_dataframe()
        
        if len(df) == 0:
            return pd.Series()
        
        # Set timestamp as index
        equity = df.set_index('timestamp')['capital']
        
        return equity
    
    def get_peak_equity(self) -> float:
        """Get peak equity reached."""
        df = self.to_dataframe()
        
        if len(df) == 0:
            return self.initial_capital
        
        return df['capital'].max()
    
    def get_current_equity(self) -> float:
        """Get current (latest) equity."""
        if not self.data:
            return self.initial_capital
        
        return self.data[-1]['capital']
    
    def get_drawdown_periods(
        self,
        min_drawdown_pct: float = 1.0
    ) -> List[dict]:
        """
        Identify drawdown periods.
        
        A drawdown period starts at a peak and ends when equity recovers
        to a new peak.
        
        Args:
            min_drawdown_pct: Minimum drawdown % to include
            
        Returns:
            List of drawdown period dictionaries
        """
        df = self.to_dataframe()
        
        if len(df) < 2:
            return []
        
        drawdowns = []
        
        # Find local peaks
        peaks = df[df['capital'] == df['peak']].index.tolist()
        
        for i in range(len(peaks) - 1):
            peak_idx = peaks[i]
            next_peak_idx = peaks[i + 1]
            
            # Get data between peaks
            period = df.iloc[peak_idx:next_peak_idx + 1]
            
            # Find trough (lowest point)
            trough_idx = period['capital'].idxmin()
            
            peak_capital = period.iloc[0]['capital']
            trough_capital = period.loc[trough_idx, 'capital']
            
            # Calculate drawdown
            drawdown_amount = peak_capital - trough_capital
            drawdown_pct = (drawdown_amount / peak_capital) * 100
            
            # Skip if below minimum
            if drawdown_pct < min_drawdown_pct:
                continue
            
            drawdowns.append({
                'peak_idx': peak_idx,
                'trough_idx': trough_idx,
                'recovery_idx': next_peak_idx,
                'peak_capital': peak_capital,
                'trough_capital': trough_capital,
                'drawdown_amount': drawdown_amount,
                'drawdown_pct': drawdown_pct,
                'duration': next_peak_idx - peak_idx,
                'peak_time': period.iloc[0]['timestamp'],
                'trough_time': period.loc[trough_idx, 'timestamp'],
                'recovery_time': period.iloc[-1]['timestamp'],
            })
        
        return drawdowns
    
    def get_underwater_chart(self) -> pd.Series:
        """
        Get underwater (drawdown) chart.
        
        Shows drawdown at each point in time.
        
        Returns:
            Series of drawdown percentages over time
        """
        df = self.to_dataframe()
        
        if len(df) == 0:
            return pd.Series()
        
        underwater = df.set_index('timestamp')['drawdown_pct']
        
        return underwater
    
    def get_rolling_returns(
        self,
        window: int = 10
    ) -> pd.Series:
        """
        Calculate rolling returns.
        
        Args:
            window: Number of periods for rolling calculation
            
        Returns:
            Series of rolling return percentages
        """
        df = self.to_dataframe()
        
        if len(df) < window:
            return pd.Series()
        
        # Calculate period returns
        df['period_return'] = df['capital'].pct_change()
        
        # Rolling mean
        rolling_returns = df['period_return'].rolling(window=window).mean() * 100
        
        return rolling_returns
    
    def get_statistics(self) -> dict:
        """
        Get comprehensive equity curve statistics.
        
        Returns:
            Dictionary with equity curve metrics
        """
        df = self.to_dataframe()
        
        if len(df) < 2:
            return {
                'total_points': len(df),
                'initial_capital': self.initial_capital,
                'final_capital': self.get_current_equity(),
            }
        
        # Basic metrics
        total_return = self.get_current_equity() - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        # Peak metrics
        peak_equity = self.get_peak_equity()
        peak_return = (peak_equity - self.initial_capital) / self.initial_capital * 100
        
        # Current drawdown
        current_drawdown = (self.get_current_equity() - peak_equity) / peak_equity * 100
        
        # Find max drawdown
        max_dd = df['drawdown_pct'].min()
        
        # Volatility (std of returns)
        returns = df['capital'].pct_change().dropna()
        volatility = returns.std() * 100 if len(returns) > 0 else 0
        
        # Win/loss periods
        winning_periods = (df['trade_pnl'] > 0).sum()
        losing_periods = (df['trade_pnl'] < 0).sum()
        
        return {
            'total_points': len(df),
            'initial_capital': self.initial_capital,
            'final_capital': self.get_current_equity(),
            'peak_capital': peak_equity,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'peak_return_pct': peak_return,
            'current_drawdown_pct': current_drawdown,
            'max_drawdown_pct': abs(max_dd),
            'volatility_pct': volatility,
            'winning_periods': int(winning_periods),
            'losing_periods': int(losing_periods),
        }
    
    def print_summary(self) -> None:
        """Print formatted equity curve summary."""
        stats = self.get_statistics()
        
        print("=" * 60)
        print("EQUITY CURVE SUMMARY")
        print("=" * 60)
        
        print(f"\n💰 CAPITAL")
        print(f"   Initial: R{stats['initial_capital']:.2f}")
        print(f"   Final: R{stats['final_capital']:.2f}")
        print(f"   Peak: R{stats['peak_capital']:.2f}")
        
        print(f"\n📈 RETURNS")
        print(f"   Total: R{stats['total_return']:+.2f} ({stats['total_return_pct']:+.2f}%)")
        print(f"   Peak: {stats['peak_return_pct']:+.2f}%")
        
        print(f"\n📉 RISK")
        print(f"   Current Drawdown: {stats['current_drawdown_pct']:.2f}%")
        print(f"   Max Drawdown: {stats['max_drawdown_pct']:.2f}%")
        print(f"   Volatility: {stats['volatility_pct']:.2f}%")
        
        print(f"\n📊 ACTIVITY")
        print(f"   Total Points: {stats['total_points']}")
        print(f"   Winning Periods: {stats['winning_periods']}")
        print(f"   Losing Periods: {stats['losing_periods']}")
        
        print("=" * 60)


def create_equity_curve_from_trades(
    trades: List[Trade],
    initial_capital: float
) -> EquityCurve:
    """
    Create equity curve from list of trades.
    
    Args:
        trades: List of completed trades (chronological order)
        initial_capital: Starting capital
        
    Returns:
        EquityCurve object with all trades added
    """
    curve = EquityCurve(initial_capital)
    
    capital = initial_capital
    
    for trade in trades:
        # Update capital
        capital += trade.pnl
        
        # Add to curve
        curve.add_trade(trade, capital)
    
    return curve


def main():
    """Test equity curve generation."""
    from backtest.trade import create_trade
    
    print("=" * 60)
    print("EQUITY CURVE TEST")
    print("=" * 60)
    
    # Create sample trades
    trades = [
        create_trade(
            "W1", datetime(2024, 1, 1), 42000, 'trend',
            datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
        ),
        create_trade(
            "L1", datetime(2024, 1, 3), 42500, 'trend',
            datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250
        ),
        create_trade(
            "W2", datetime(2024, 1, 5), 41500, 'range',
            datetime(2024, 1, 6), 42000, 'trend', 'exit', 250
        ),
        create_trade(
            "W3", datetime(2024, 1, 8), 42000, 'trend',
            datetime(2024, 1, 9), 42400, 'trend', 'exit', 250
        ),
        create_trade(
            "L2", datetime(2024, 1, 10), 42400, 'trend',
            datetime(2024, 1, 10), 41580, 'range', 'stop_loss', 250
        ),
    ]
    
    # Create equity curve
    curve = create_equity_curve_from_trades(trades, 500)
    
    # Print summary
    curve.print_summary()
    
    # Show equity progression
    print("\n📊 EQUITY PROGRESSION")
    df = curve.to_dataframe()
    
    print(df[['timestamp', 'capital', 'trade_pnl', 'drawdown_pct', 'return_pct']].to_string(index=False))
    
    # Drawdown periods
    print("\n📉 DRAWDOWN PERIODS")
    drawdowns = curve.get_drawdown_periods(min_drawdown_pct=0.5)
    
    if drawdowns:
        for i, dd in enumerate(drawdowns, 1):
            print(f"\nDrawdown #{i}:")
            print(f"   Peak: R{dd['peak_capital']:.2f} at {dd['peak_time'].date()}")
            print(f"   Trough: R{dd['trough_capital']:.2f} at {dd['trough_time'].date()}")
            print(f"   Recovery: {dd['recovery_time'].date()}")
            print(f"   Drawdown: {dd['drawdown_pct']:.2f}%")
            print(f"   Duration: {dd['duration']} trades")
    else:
        print("   No significant drawdown periods")
    
    print("\n" + "=" * 60)
    print("✅ Equity curve test complete")


if __name__ == "__main__":
    main()
"""
Backtest result container.

Holds all results from a backtest execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from backtest.metrics import PerformanceMetrics

import pandas as pd

from backtest.trade import Trade


@dataclass
class BacktestResult:
    """
    Complete results from backtest execution.
    
    Contains:
    - Summary statistics
    - Performance metrics
    - All trades
    - Equity curve
    - Regime analysis
    """
    
    # Time period
    start_date: datetime
    end_date: datetime
    
    # Capital
    initial_capital: float
    final_capital: float
    
    # All trades
    trades: List[Trade] = field(default_factory=list)
    
    # Equity curve (time series of capital)
    equity_curve: Optional[pd.DataFrame] = None
    
    # Performance metrics (calculated)
    total_return: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    sharpe_ratio: float = 0.0
    
    # Trade statistics (calculated)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Returns (calculated)
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    
    # Regime performance (calculated)
    regime_performance: Dict[str, Dict] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived metrics."""
        self.calculate_metrics()
    
    @property
    def duration_days(self) -> int:
        """Calculate backtest duration in days."""
        delta = self.end_date - self.start_date
        return delta.days
    
    def calculate_metrics(self) -> None:
        """
        Calculate all derived metrics from trades using centralized PerformanceMetrics.
        """
        if not self.trades:
        # Calculate capital metrics even if no trades were taken
            self.total_return = self.final_capital - self.initial_capital
            if self.initial_capital > 0:
                self.total_return_pct = (self.total_return / self.initial_capital) * 100
            return

    # Use PerformanceMetrics for calculations if equity curve is available
        if self.equity_curve is not None and not self.equity_curve.empty:
            all_metrics = PerformanceMetrics.calculate_all_metrics(
                trades=self.trades,
                equity_curve=self.equity_curve,
                initial_capital=self.initial_capital,
                final_capital=self.final_capital,
                start_date=self.start_date,
                end_date=self.end_date
            )
                
        # Update self with calculated metrics
            self.total_return = all_metrics.get('total_return', 0.0)
            self.total_return_pct = all_metrics.get('total_return_pct', 0.0)
            self.sharpe_ratio = all_metrics.get('sharpe_ratio', 0.0)
            self.max_drawdown = all_metrics.get('max_drawdown_pct', 0.0)
            self.total_trades = all_metrics.get('total_trades', 0)
            self.win_rate = all_metrics.get('win_rate', 0.0)
            self.profit_factor = all_metrics.get('profit_factor', 0.0)
            self.expectancy = all_metrics.get('expectancy', 0.0)
            self.average_win = all_metrics.get('average_win', 0.0)
            self.average_loss = all_metrics.get('average_loss', 0.0)
        else:
        # Fallback to basic calculations if equity_curve is missing
            self.total_trades = len(self.trades)
            self.winning_trades = sum(1 for t in self.trades if t.is_winner)
            self.losing_trades = self.total_trades - self.winning_trades
            self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        
            self.total_return = self.final_capital - self.initial_capital
            if self.initial_capital > 0:
                self.total_return_pct = (self.total_return / self.initial_capital) * 100
    
    def get_summary(self) -> Dict:
        """Get summary statistics as dictionary."""
        return {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'duration_days': self.duration_days,
            },
            'capital': {
                'initial': self.initial_capital,
                'final': self.final_capital,
                'return': self.total_return,
                'return_pct': self.total_return_pct,
            },
            'performance': {
                'sharpe_ratio': self.sharpe_ratio,
                'max_drawdown': self.max_drawdown,
                'max_drawdown_duration': self.max_drawdown_duration,
            },
            'trades': {
                'total': self.total_trades,
                'winners': self.winning_trades,
                'losers': self.losing_trades,
                'win_rate': self.win_rate,
            },
            'returns': {
                'average_win': self.average_win,
                'average_loss': self.average_loss,
                'profit_factor': self.profit_factor,
                'expectancy': self.expectancy,
            }
        }
    
    def print_summary(self) -> None:
        """Print formatted summary."""
        print("=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        
        print(f"\n📅 PERIOD")
        print(f"   Start: {self.start_date.date()}")
        print(f"   End: {self.end_date.date()}")
        print(f"   Duration: {self.duration_days} days")
        
        print(f"\n💰 CAPITAL")
        print(f"   Initial: R{self.initial_capital:.2f}")
        print(f"   Final: R{self.final_capital:.2f}")
        print(f"   Return: R{self.total_return:+.2f} ({self.total_return_pct:+.2f}%)")
        
        print(f"\n📊 PERFORMANCE")
        print(f"   Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"   Max Drawdown: {self.max_drawdown:.2f}%")
        
        print(f"\n📈 TRADES")
        print(f"   Total: {self.total_trades}")
        print(f"   Winners: {self.winning_trades} ({self.win_rate*100:.1f}%)")
        print(f"   Losers: {self.losing_trades}")
        
        print(f"\n💵 RETURNS")
        print(f"   Avg Win: R{self.average_win:+.2f}")
        print(f"   Avg Loss: R{self.average_loss:+.2f}")
        print(f"   Profit Factor: {self.profit_factor:.2f}")
        print(f"   Expectancy: R{self.expectancy:+.2f}")
        
        print("\n" + "=" * 60)


def main():
    """Test result creation."""
    from backtest.trade import create_trade
    
    print("=" * 60)
    print("BACKTEST RESULT TEST")
    print("=" * 60)
    
    # Create sample trades
    trades = [
        create_trade(
            "WIN_1", datetime(2024, 1, 1), 42000, 'trend',
            datetime(2024, 1, 2), 42500, 'trend', 'exit', 250
        ),
        create_trade(
            "LOSS_1", datetime(2024, 1, 3), 42500, 'trend',
            datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250
        ),
        create_trade(
            "WIN_2", datetime(2024, 1, 5), 41500, 'range',
            datetime(2024, 1, 6), 42000, 'trend', 'exit', 250
        ),
    ]
    
    # Create result
    result = BacktestResult(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 7),
        initial_capital=500,
        final_capital=502.5,
        trades=trades
    )
    
    # Print summary
    result.print_summary()
    
    print("\n✅ Result test complete")


if __name__ == "__main__":
    main()
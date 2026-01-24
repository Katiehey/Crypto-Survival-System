"""
Performance metrics calculator for backtesting.

Calculates:
- Sharpe ratio
- Maximum drawdown
- Profit factor
- Expectancy
- Win/loss statistics
- Return metrics
"""

from typing import List, Tuple, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from backtest.trade import Trade


class PerformanceMetrics:
    """
    Calculate backtest performance metrics.
    
    All calculations are based on completed trades and equity curve.
    """
    
    @staticmethod
    def sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 8760  # Hourly data: 365 * 24
    ) -> float:
        """
        Calculate Sharpe ratio.
        
        Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns
        
        Args:
            returns: Series of period returns
            risk_free_rate: Annual risk-free rate (default: 0)
            periods_per_year: Number of periods in a year (8760 for hourly)
            
        Returns:
            Annualized Sharpe ratio
            
        Example:
            >>> returns = pd.Series([0.01, -0.005, 0.02, 0.015])
            >>> sharpe = PerformanceMetrics.sharpe_ratio(returns)
        """
        if len(returns) < 2:
            return 0.0
        
        # Remove NaN values
        returns = returns.dropna()
        
        if len(returns) < 2:
            return 0.0
        
        # Calculate excess returns
        excess_returns = returns - (risk_free_rate / periods_per_year)
        
        # Calculate mean and std
        mean_return = excess_returns.mean()
        std_return = excess_returns.std()
        
        if std_return == 0:
            return 0.0
        
        # Sharpe ratio (annualized)
        sharpe = (mean_return / std_return) * np.sqrt(periods_per_year)
        
        return sharpe
    
    @staticmethod
    def max_drawdown(equity_curve: pd.Series) -> Tuple[float, int, int, int]:
        """
        Calculate maximum drawdown.
        
        Drawdown is the peak-to-trough decline in equity.
        
        Args:
            equity_curve: Series of equity values over time
            
        Returns:
            Tuple of (max_drawdown_pct, max_dd_duration, start_idx, end_idx)
            
        Example:
            >>> equity = pd.Series([100, 110, 105, 95, 100, 115])
            >>> max_dd, duration, start, end = PerformanceMetrics.max_drawdown(equity)
        """
        if len(equity_curve) < 2:
            return 0.0, 0, 0, 0
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown at each point
        drawdown = (equity_curve - running_max) / running_max
        
        # Find maximum drawdown
        max_dd = drawdown.min()
        max_dd_idx = drawdown.idxmin()
        
        # Find start of drawdown (last peak before max dd)
        start_idx = 0
        if max_dd_idx > 0:
            # Find the peak before the trough
            before_trough = equity_curve.iloc[:max_dd_idx + 1]
            start_idx = before_trough.idxmax()
        
        # Find end of drawdown (recovery to new high, or end of data)
        end_idx = len(equity_curve) - 1
        if max_dd_idx < len(equity_curve) - 1:
            # Look for recovery after trough
            after_trough = equity_curve.iloc[max_dd_idx:]
            peak_value = equity_curve.iloc[start_idx]
            
            # Find first point that exceeds previous peak
            recovery = after_trough[after_trough >= peak_value]
            if len(recovery) > 0:
                end_idx = recovery.index[0]
        
        # Calculate duration
        duration = end_idx - start_idx
        
        return abs(max_dd) * 100, duration, start_idx, end_idx
    
    @staticmethod
    def profit_factor(trades: List[Trade]) -> float:
        """
        Calculate profit factor.
        
        Profit Factor = Total Wins / Total Losses
        
        Args:
            trades: List of completed trades
            
        Returns:
            Profit factor (>1 = profitable system)
        """
        if not trades:
            return 0.0
        
        total_wins = sum(t.pnl for t in trades if t.is_winner)
        total_losses = abs(sum(t.pnl for t in trades if not t.is_winner))
        
        if total_losses == 0:
            return float('inf') if total_wins > 0 else 0.0
        
        return total_wins / total_losses
    
    @staticmethod
    def expectancy(trades: List[Trade]) -> float:
        """
        Calculate expectancy per trade.
        
        Expectancy = Average PnL per trade
        
        Args:
            trades: List of completed trades
            
        Returns:
            Expected value per trade
        """
        if not trades:
            return 0.0
        
        total_pnl = sum(t.pnl for t in trades)
        return total_pnl / len(trades)
    
    @staticmethod
    def win_rate(trades: List[Trade]) -> float:
        """
        Calculate win rate.
        
        Args:
            trades: List of completed trades
            
        Returns:
            Win rate as decimal (0-1)
        """
        if not trades:
            return 0.0
        
        winners = sum(1 for t in trades if t.is_winner)
        return winners / len(trades)
    
    @staticmethod
    def average_win_loss(trades: List[Trade]) -> Tuple[float, float]:
        """
        Calculate average win and average loss.
        
        Args:
            trades: List of completed trades
            
        Returns:
            Tuple of (average_win, average_loss)
        """
        if not trades:
            return 0.0, 0.0
        
        winners = [t.pnl for t in trades if t.is_winner]
        losers = [t.pnl for t in trades if not t.is_winner]
        
        avg_win = sum(winners) / len(winners) if winners else 0.0
        avg_loss = sum(losers) / len(losers) if losers else 0.0
        
        return avg_win, avg_loss
    
    @staticmethod
    def calculate_returns(equity_curve: pd.Series) -> pd.Series:
        """
        Calculate period returns from equity curve.
        
        Args:
            equity_curve: Series of equity values
            
        Returns:
            Series of period returns
        """
        returns = equity_curve.pct_change()
        return returns.fillna(0)
    
    @staticmethod
    def total_return(initial: float, final: float) -> Tuple[float, float]:
        """
        Calculate total return.
        
        Args:
            initial: Initial capital
            final: Final capital
            
        Returns:
            Tuple of (absolute_return, percent_return)
        """
        absolute_return = final - initial
        percent_return = (absolute_return / initial) * 100 if initial > 0 else 0
        
        return absolute_return, percent_return
    
    @staticmethod
    def annualized_return(
        total_return_pct: float,
        days: int
    ) -> float:
        """
        Calculate annualized return.
        
        Args:
            total_return_pct: Total return as percentage
            days: Number of days in backtest
            
        Returns:
            Annualized return percentage
        """
        if days <= 0:
            return 0.0
        
        # Convert to decimal
        total_return_decimal = total_return_pct / 100
        
        # Annualize
        years = days / 365.25
        if years <= 0:
            return 0.0
        
        annualized = ((1 + total_return_decimal) ** (1 / years) - 1) * 100
        
        return annualized
    
    @staticmethod
    def consecutive_wins_losses(trades: List[Trade]) -> Tuple[int, int]:
        """
        Calculate maximum consecutive wins and losses.
        
        Args:
            trades: List of completed trades (chronological order)
            
        Returns:
            Tuple of (max_consecutive_wins, max_consecutive_losses)
        """
        if not trades:
            return 0, 0
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in trades:
            if trade.is_winner:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
        
        return max_wins, max_losses
    
    @staticmethod
    def calculate_all_metrics(
        trades: List[Trade],
        equity_curve: pd.Series,
        initial_capital: float,
        final_capital: float,
        start_date: datetime,
        end_date: datetime
    ) -> dict:
        """
        Calculate all performance metrics.
        
        Args:
            trades: List of all trades
            equity_curve: Equity over time
            initial_capital: Starting capital
            final_capital: Ending capital
            start_date: Backtest start
            end_date: Backtest end
            
        Returns:
            Dictionary with all metrics
        """
        # Basic metrics
        total_ret, total_ret_pct = PerformanceMetrics.total_return(
            initial_capital, final_capital
        )
        
        # Trade statistics
        win_rt = PerformanceMetrics.win_rate(trades)
        avg_win, avg_loss = PerformanceMetrics.average_win_loss(trades)
        pf = PerformanceMetrics.profit_factor(trades)
        exp = PerformanceMetrics.expectancy(trades)
        max_wins, max_losses = PerformanceMetrics.consecutive_wins_losses(trades)
        
        # Advanced metrics
        returns = PerformanceMetrics.calculate_returns(equity_curve)
        sharpe = PerformanceMetrics.sharpe_ratio(returns)
        max_dd, dd_duration, dd_start, dd_end = PerformanceMetrics.max_drawdown(
            equity_curve
        )
        
        # Time-based metrics
        days = (end_date - start_date).days
        ann_return = PerformanceMetrics.annualized_return(total_ret_pct, days)
        
        return {
            'total_return': total_ret,
            'total_return_pct': total_ret_pct,
            'annualized_return_pct': ann_return,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_dd,
            'max_drawdown_duration': dd_duration,
            'win_rate': win_rt,
            'profit_factor': pf,
            'expectancy': exp,
            'average_win': avg_win,
            'average_loss': avg_loss,
            'max_consecutive_wins': max_wins,
            'max_consecutive_losses': max_losses,
            'total_trades': len(trades),
        }


def main():
    """Test performance metrics."""
    from backtest.trade import create_trade
    
    print("=" * 60)
    print("PERFORMANCE METRICS TEST")
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
    ]
    
    # Create sample equity curve
    equity = pd.Series([
        500, 502.5, 497.5, 502.5, 505.0
    ])
    
    # Calculate metrics
    print("\n📊 CALCULATING METRICS...")
    
    metrics = PerformanceMetrics.calculate_all_metrics(
        trades=trades,
        equity_curve=equity,
        initial_capital=500,
        final_capital=505,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 10)
    )
    
    print("\n💰 RETURNS")
    print(f"   Total: ${metrics['total_return']:+.2f} ({metrics['total_return_pct']:+.2f}%)")
    print(f"   Annualized: {metrics['annualized_return_pct']:+.2f}%")
    
    print("\n📈 RISK METRICS")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"   Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"   DD Duration: {metrics['max_drawdown_duration']} periods")
    
    print("\n🎯 TRADE STATISTICS")
    print(f"   Win Rate: {metrics['win_rate']*100:.1f}%")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Expectancy: ${metrics['expectancy']:+.2f}")
    
    print("\n💵 WIN/LOSS")
    print(f"   Avg Win: ${metrics['average_win']:+.2f}")
    print(f"   Avg Loss: ${metrics['average_loss']:+.2f}")
    print(f"   Max Consecutive Wins: {metrics['max_consecutive_wins']}")
    print(f"   Max Consecutive Losses: {metrics['max_consecutive_losses']}")
    
    print("\n" + "=" * 60)
    print("✅ Performance metrics test complete")


if __name__ == "__main__":
    main()
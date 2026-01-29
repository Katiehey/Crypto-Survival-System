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
from scipy import stats

from backtest import equity_curve
from backtest import equity_curve
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
        # 1. Extract values safely
        if isinstance(equity_curve, pd.DataFrame) and 'capital' in equity_curve.columns:
            values = equity_curve['capital'].values
            index = equity_curve.index
        else:
            values = equity_curve.values
            index = equity_curve.index

        if len(values) == 0:
            return 0.0, 0, None, None
    
    # 2. Calculate drawdown array
        rolling_max = np.maximum.accumulate(values)
    # Avoid division by zero if capital ever hits 0
        drawdowns = np.where(rolling_max > 0, (rolling_max - values) / rolling_max, 0.0)
    
        max_dd_pct = np.max(drawdowns) * 100  # Result is e.g. 5.4%
        max_dd_pos = np.argmax(drawdowns)
    
        if max_dd_pct <= 0:
            return 0.0, 0, index[0], index[0]

    # 3. Find the peak that preceded the max drawdown
        peak_pos = np.argmax(values[:max_dd_pos + 1])
    
        peak_idx = index[peak_pos]
        end_idx = index[max_dd_pos]
    
    # Calculate duration (number of periods)
        duration = int(max_dd_pos - peak_pos)
    
        return float(max_dd_pct), duration, peak_idx, end_idx
    
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
        if 'capital' in equity_curve.columns:
            returns = equity_curve['capital'].pct_change().dropna()
        else:
        # Fallback if it's already a Series
            returns = equity_curve.pct_change().dropna()
        return returns
    
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
            'largest_win': max([t.pnl for t in trades if t.is_winner] or [0.0]),
            'largest_loss': min([t.pnl for t in trades if not t.is_winner] or [0.0]),
        }
    
    @staticmethod
    def calmar_ratio(total_return_pct: float, max_drawdown_pct: float) -> float:
        """
        Calculate Calmar Ratio (return to max drawdown ratio).
        
        Args:
            total_return_pct: Total return percentage
            max_drawdown_pct: Maximum drawdown percentage
            
        Returns:
            Calmar ratio, or 0 if drawdown is 0
        """
        if max_drawdown_pct == 0:
            return 0.0
        return total_return_pct / abs(max_drawdown_pct)
    
    @staticmethod
    def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino Ratio (return to downside deviation).
        
        Args:
            returns: Series of returns
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sortino ratio
        """
        if len(returns) < 2:
            return 0.0
        
        # Convert to daily if needed
        # Assuming daily returns for now
        annual_factor = np.sqrt(252)  # Daily to annual
        
        # Calculate downside deviation
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf')  # No downside risk
        
        downside_std = downside_returns.std()
        if downside_std == 0:
            return float('inf')
        
        # Annualized metrics
        avg_return = returns.mean() * 252  # Annualized return
        downside_deviation = downside_std * annual_factor
        
        # Sortino ratio
        sortino = (avg_return - risk_free_rate) / downside_deviation
        
        return sortino
    
    @staticmethod
    def value_at_risk(returns: pd.Series, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            returns: Series of returns
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            VaR at specified confidence level (negative = loss)
        """
        if len(returns) < 10:
            return 0.0
        
        # Historical VaR
        var = np.percentile(returns, (1 - confidence_level) * 100)
        
        return var
    
    @staticmethod
    def expected_shortfall(returns: pd.Series, confidence_level: float = 0.95) -> float:
        """
        Calculate Expected Shortfall (CVaR).
        
        Args:
            returns: Series of returns
            confidence_level: Confidence level
            
        Returns:
            Expected shortfall
        """
        if len(returns) < 10:
            return 0.0
        
        var = PerformanceMetrics.value_at_risk(returns, confidence_level)
        # Average of returns worse than VaR
        tail_returns = returns[returns <= var]
        
        if len(tail_returns) == 0:
            return var
        
        return tail_returns.mean()
    
    @staticmethod
    def ulcer_index(equity: pd.Series, period: int = 14) -> float:
        """
        Calculate Ulcer Index (measure of downside risk).
        
        Args:
            equity: Series of equity values
            period: Lookback period for peak
            
        Returns:
            Ulcer Index
        """
        if len(equity) < period:
            return 0.0
        
        # Calculate drawdown from highest peak in period
        drawdowns = []
        for i in range(period, len(equity)):
            period_high = equity.iloc[i-period:i].max()
            drawdown = (equity.iloc[i] - period_high) / period_high
            drawdowns.append(drawdown ** 2)  # Square for ulcer index
        
        if not drawdowns:
            return 0.0
        
        ulcer = np.sqrt(np.mean(drawdowns))
        
        return ulcer
    
    @staticmethod
    def recovery_factor(total_return: float, max_drawdown: float) -> float:
        """
        Calculate Recovery Factor (return per unit of drawdown).
        
        Args:
            total_return: Total return amount
            max_drawdown: Maximum drawdown amount
            
        Returns:
            Recovery factor
        """
        if max_drawdown == 0:
            return float('inf') if total_return > 0 else 0.0
        
        return total_return / abs(max_drawdown)
    
    @staticmethod
    def risk_of_ruin(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        risk_per_trade: float
    ) -> float:
        """
        Calculate Risk of Ruin probability.
        
        Args:
            win_rate: Probability of winning
            avg_win: Average win amount
            avg_loss: Average loss amount
            risk_per_trade: Risk amount per trade
            
        Returns:
            Probability of ruin (0-1)
        """
        if win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        # Simplified risk of ruin calculation
        p = win_rate
        q = 1 - p
        avg_win_ratio = avg_win / risk_per_trade
        avg_loss_ratio = abs(avg_loss) / risk_per_trade
        
        # Avoid division by zero
        if avg_loss_ratio == 0:
            return 0.0
        
        # Risk of ruin formula
        try:
            A = (1 - p) / p
            ruin_prob = ((1 - A ** avg_win_ratio) / (1 - A ** (avg_win_ratio + avg_loss_ratio)))
            ruin_prob = max(0.0, min(1.0, ruin_prob))
        except (ZeroDivisionError, ValueError):
            ruin_prob = 0.0
        
        return ruin_prob
    
    @staticmethod
    def kelly_criterion(win_rate: float, win_loss_ratio: float, capped: bool = True) -> float:
        """
        Calculate Kelly Criterion optimal bet size.
        
        Args:
            win_rate: Probability of winning
            win_loss_ratio: Ratio of average win to average loss
            
        Returns:
            Kelly percentage (0-1)
        """
        if win_loss_ratio <= 0:
            return 0.0
        
        kelly = win_rate - ((1 - win_rate) / win_loss_ratio)
        
        if capped:
            return max(0.0, min(0.25, kelly))
        return kelly
    
    @staticmethod
    def calculate_all_advanced_metrics(
        trades: List,
        equity_series: pd.Series,
        returns_series: pd.Series
    ) -> dict:
        """
        Calculate all advanced performance metrics.
        
        Args:
            trades: List of Trade objects
            equity_series: Series of equity values over time
            returns_series: Series of returns
            
        Returns:
            Dictionary with all advanced metrics
        """
        if len(trades) == 0 or len(equity_series) < 2:
            return {}
        
        # Basic metrics needed for calculations
        total_return = sum(t.pnl for t in trades)
        total_return_pct = (equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0] * 100
        
        # Max drawdown
        max_dd, _, _, _ = PerformanceMetrics.max_drawdown(equity_series)
        
        # Win rate and averages
        win_rate = PerformanceMetrics.win_rate(trades)
        winning_trades = [t for t in trades if t.is_winner]
        losing_trades = [t for t in trades if not t.is_winner]
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        # Calculate all advanced metrics
        metrics = {
            'calmar_ratio': PerformanceMetrics.calmar_ratio(total_return_pct, max_dd),
            'sortino_ratio': PerformanceMetrics.sortino_ratio(returns_series),
            'value_at_risk_95': PerformanceMetrics.value_at_risk(returns_series, 0.95),
            'expected_shortfall_95': PerformanceMetrics.expected_shortfall(returns_series, 0.95),
            'ulcer_index': PerformanceMetrics.ulcer_index(equity_series),
            'recovery_factor': PerformanceMetrics.recovery_factor(total_return, max_dd),
            'risk_of_ruin': PerformanceMetrics.risk_of_ruin(
                win_rate, avg_win, avg_loss, abs(avg_loss) if avg_loss != 0 else 1.0
            ),
            'kelly_criterion': PerformanceMetrics.kelly_criterion(win_rate, win_loss_ratio),
            'gain_to_pain_ratio': total_return / abs(sum(t.pnl for t in losing_trades)) if losing_trades else float('inf'),
            'profit_per_day': total_return / (len(equity_series) / 24) if len(equity_series) > 0 else 0,  # Assuming hourly data
        }
        
        return metrics


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
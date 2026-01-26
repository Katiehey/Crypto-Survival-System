# backtest/visualization.py
"""
Visualization tools for backtest results.
Generates plots and charts for analysis.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from typing import Optional, Tuple, List
import os

plt.style.use('seaborn-v0_8-darkgrid')


class BacktestVisualizer:
    """
    Create visualizations for backtest results.
    
    Generates:
    - Equity curve with drawdown
    - Returns distribution
    - Monthly returns heatmap
    - Trade analysis plots
    """
    
    def __init__(self, output_dir: str = "backtest_plots"):
        """
        Initialize visualizer.
        
        Args:
            output_dir: Directory to save plots
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def plot_equity_curve(
        self,
        equity_series: pd.Series,
        title: str = "Equity Curve",
        save: bool = True
    ) -> plt.Figure:
        """
        Plot equity curve with drawdown.
        
        Args:
            equity_series: Series of equity values over time
            title: Plot title
            save: Whether to save the plot
            
        Returns:
            Matplotlib figure
        """
        if len(equity_series) < 2:
            print("⚠️  Not enough data for equity curve")
            return None
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[3, 1])
        
        # Plot equity curve
        ax1.plot(equity_series.index, equity_series.values, 
                linewidth=2, color='green', alpha=0.7)
        ax1.fill_between(equity_series.index, equity_series.values, 
                        equity_series.iloc[0], alpha=0.2, color='green')
        
        # Mark start and end
        ax1.scatter([equity_series.index[0], equity_series.index[-1]],
                   [equity_series.iloc[0], equity_series.iloc[-1]],
                   color='red', s=100, zorder=5)
        
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.set_ylabel('Capital (R)', fontsize=12)
        ax1.grid(True, alpha=0.3)
        
        # Calculate and plot drawdown
        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak * 100
        
        ax2.fill_between(equity_series.index, drawdown.values, 0,
                        where=drawdown < 0, color='red', alpha=0.5)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        
        ax2.set_ylabel('Drawdown (%)', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.grid(True, alpha=0.3)
        
        # Format x-axis
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        if save:
            filename = os.path.join(self.output_dir, "equity_curve.png")
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"✅ Saved equity curve to: {filename}")
        
        return fig
    
    def plot_returns_distribution(
        self,
        returns: pd.Series,
        title: str = "Returns Distribution",
        save: bool = True
    ) -> plt.Figure:
        """
        Plot distribution of returns.
        
        Args:
            returns: Series of returns
            title: Plot title
            save: Whether to save the plot
            
        Returns:
            Matplotlib figure
        """
        if len(returns) < 10:
            print("⚠️  Not enough data for returns distribution")
            return None
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # Histogram
        ax1.hist(returns.values, bins=30, edgecolor='black', alpha=0.7, color='blue')
        ax1.axvline(x=returns.mean(), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {returns.mean():.2%}')
        ax1.axvline(x=0, color='green', linestyle='-', linewidth=1)
        
        ax1.set_title('Returns Histogram', fontsize=12)
        ax1.set_xlabel('Return', fontsize=10)
        ax1.set_ylabel('Frequency', fontsize=10)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Box plot
        ax2.boxplot(returns.values, vert=True)
        ax2.set_title('Returns Box Plot', fontsize=12)
        ax2.set_ylabel('Return', fontsize=10)
        ax2.grid(True, alpha=0.3)
        
        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if save:
            filename = os.path.join(self.output_dir, "returns_distribution.png")
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"✅ Saved returns distribution to: {filename}")
        
        return fig
    
    def plot_monthly_returns(
        self,
        equity_series: pd.Series,
        title: str = "Monthly Returns",
        save: bool = True
    ) -> plt.Figure:
        """
        Plot monthly returns heatmap.
        
        Args:
            equity_series: Series of equity values
            title: Plot title
            save: Whether to save the plot
            
        Returns:
            Matplotlib figure
        """
        if len(equity_series) < 30:
            print("⚠️  Not enough data for monthly returns")
            return None
        
        # Resample to daily if needed, then calculate monthly returns
        try:
            daily_returns = equity_series.resample('D').last().pct_change().dropna()
            monthly_returns = daily_returns.resample('ME').apply(
                lambda x: (1 + x).prod() - 1
            ).to_frame(name='Returns')
        except Exception as e:
            print(f"❌ Resampling error: {e}")
            return None
        
        # Create pivot table for heatmap
        monthly_returns.index = pd.to_datetime(monthly_returns.index)
        monthly_returns['Year'] = monthly_returns.index.year
        monthly_returns['Month'] = monthly_returns.index.month
        
        pivot = monthly_returns.pivot_table(
            values='Returns', index='Year', columns='Month', aggfunc='mean'
        )
        
        if pivot.empty:
            return None
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Create heatmap
        im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto', vmin=-0.1, vmax=0.1)
        
        # Add labels
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][:len(pivot.columns)])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        
        # Add text annotations
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot.iloc[i, j]
                if not np.isnan(val):
                    color = 'white' if abs(val) > 0.05 else 'black'
                    ax.text(j, i, f'{val:.1%}', ha='center', va='center', 
                           color=color, fontsize=8)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Year', fontsize=12)
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Monthly Return', fontsize=10)
        
        plt.tight_layout()
        
        if save:
            filename = os.path.join(self.output_dir, "monthly_returns.png")
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"✅ Saved monthly returns to: {filename}")
        
        return fig
    
    def plot_trade_analysis(
        self,
        trades: List,
        title: str = "Trade Analysis",
        save: bool = True
    ) -> plt.Figure:
        """
        Plot trade analysis charts.
        
        Args:
            trades: List of Trade objects
            title: Plot title
            save: Whether to save the plot
            
        Returns:
            Matplotlib figure
        """
        if len(trades) < 5:
            print("⚠️  Not enough trades for analysis")
            return None
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. PnL by trade
        pnls = [t.pnl for t in trades]
        trade_ids = range(1, len(trades) + 1)
        
        colors = ['green' if pnl > 0 else 'red' for pnl in pnls]
        ax1.bar(trade_ids, pnls, color=colors, alpha=0.7, edgecolor='black')
        ax1.axhline(y=0, color='black', linewidth=0.5)
        ax1.set_title('PnL by Trade', fontsize=12)
        ax1.set_xlabel('Trade #', fontsize=10)
        ax1.set_ylabel('PnL (R)', fontsize=10)
        ax1.grid(True, alpha=0.3)
        
        # 2. Cumulative PnL
        cumulative_pnl = np.cumsum(pnls)
        ax2.plot(trade_ids, cumulative_pnl, linewidth=2, color='blue')
        ax2.fill_between(trade_ids, 0, cumulative_pnl, alpha=0.2, color='blue')
        ax2.set_title('Cumulative PnL', fontsize=12)
        ax2.set_xlabel('Trade #', fontsize=10)
        ax2.set_ylabel('Cumulative PnL (R)', fontsize=10)
        ax2.grid(True, alpha=0.3)
        
        # 3. Win/Loss distribution
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl <= 0]
        
        if wins:
            ax3.hist(wins, bins=15, alpha=0.7, color='green', 
                    label=f'Wins: {len(wins)}', edgecolor='black')
        if losses:
            ax3.hist(losses, bins=15, alpha=0.7, color='red',
                    label=f'Losses: {len(losses)}', edgecolor='black')
        
        ax3.axvline(x=0, color='black', linewidth=1)
        ax3.set_title('Win/Loss Distribution', fontsize=12)
        ax3.set_xlabel('PnL (R)', fontsize=10)
        ax3.set_ylabel('Frequency', fontsize=10)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. Trade duration distribution
        durations = [t.duration for t in trades]
        ax4.hist(durations, bins=15, alpha=0.7, color='purple', edgecolor='black')
        ax4.set_title('Trade Duration Distribution', fontsize=12)
        ax4.set_xlabel('Duration (hours)', fontsize=10)
        ax4.set_ylabel('Frequency', fontsize=10)
        ax4.grid(True, alpha=0.3)
        
        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if save:
            filename = os.path.join(self.output_dir, "trade_analysis.png")
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"✅ Saved trade analysis to: {filename}")
        
        return fig
    
    def plot_all(
        self,
        equity_series: pd.Series,
        trades: List,
        title_prefix: str = ""
    ) -> None:
        """
        Generate all plots.
        
        Args:
            equity_series: Series of equity values
            trades: List of Trade objects
            title_prefix: Prefix for plot titles
        """
        print("\n📊 Generating visualizations...")
        
        # Calculate returns
        returns = equity_series.pct_change().dropna()
        
        # Generate all plots
        self.plot_equity_curve(
            equity_series, 
            title=f"{title_prefix}Equity Curve"
        )
        
        self.plot_returns_distribution(
            returns,
            title=f"{title_prefix}Returns Distribution"
        )
        
        self.plot_monthly_returns(
            equity_series,
            title=f"{title_prefix}Monthly Returns"
        )
        
        self.plot_trade_analysis(
            trades,
            title=f"{title_prefix}Trade Analysis"
        )
        
        print(f"\n✅ All visualizations saved to: {self.output_dir}/")


def main():
    """Test visualizer with sample data."""
    print("=" * 60)
    print("BACKTEST VISUALIZER TEST")
    print("=" * 60)
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='h')
    equity = 500 + np.cumsum(np.random.randn(100) * 2)
    equity_series = pd.Series(equity, index=dates)
    
    # Create sample trades
    from backtest.trade import create_trade
    from datetime import datetime
    
    trades = []
    for i in range(20):
        is_winner = np.random.random() > 0.4
        pnl = np.random.randn() * 5 + (3 if is_winner else -2)
        
        # Create simplified trade for testing
        trade = create_trade(
            f"TEST_{i}",
            datetime(2024, 1, 1 + i//3),
            42000 + np.random.randn() * 1000,
            'trend',
            datetime(2024, 1, 1 + i//3, np.random.randint(1, 24)),
            42000 + np.random.randn() * 1000 + (500 if is_winner else -500),
            'trend',
            'exit',
            250
        )
        
        # Override PnL for testing
        trade.pnl = pnl
        trades.append(trade)
    
    # Create visualizer
    visualizer = BacktestVisualizer(output_dir="test_plots")
    
    # Generate all plots
    visualizer.plot_all(equity_series, trades, "Test: ")
    
    print("\n" + "=" * 60)
    print("✅ Visualization test complete")
    print("=" * 60)


if __name__ == "__main__":
    # Only run if matplotlib is available
    try:
        import matplotlib
        main()
    except ImportError:
        print("⚠️  Matplotlib not installed. Install with: pip install matplotlib")
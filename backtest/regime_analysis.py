# backtest/regime_analysis.py
"""
Regime-based performance analysis for backtesting.

Analyzes strategy performance by market regime.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from collections import defaultdict

from backtest.trade import Trade
from regime.classifier import Regime


class RegimeAnalyzer:
    """
    Analyze trading performance by market regime.
    
    Provides:
    - Performance breakdown by entry/exit regime
    - Regime transition analysis
    - Best/worst performing regimes
    - Regime-specific statistics
    """
    
    def __init__(self):
        """Initialize regime analyzer."""
        self.regime_stats = {}
    
    def analyze_trades(self, trades: List[Trade]) -> Dict:
        """
        Analyze trades by regime.
        
        Args:
            trades: List of completed trades
            
        Returns:
            Dictionary with regime-based statistics
        """
        if not trades:
            return self._create_empty_stats()
        
        # Initialize statistics
        stats = {
            'by_entry_regime': defaultdict(lambda: self._init_regime_stats()),
            'by_exit_regime': defaultdict(lambda: self._init_regime_stats()),
            'by_regime_transition': defaultdict(lambda: self._init_regime_stats()),
            'overall': self._init_regime_stats()
        }
        
        # Analyze each trade
        for trade in trades:
            self._analyze_trade(trade, stats)
        
        # Calculate derived metrics
        self._calculate_derived_metrics(stats)
        
        return stats
    
    def _init_regime_stats(self) -> Dict:
        """Initialize empty regime statistics."""
        return {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'winning_pnl': 0.0,
            'losing_pnl': 0.0,
            'largest_win': -float('inf'),
            'largest_loss': float('inf'),
            'avg_trade_duration': 0.0,
            'durations': []
        }
    
    def _analyze_trade(self, trade: Trade, stats: Dict) -> None:
        """Analyze single trade and update statistics."""
        # Overall statistics
        stats['overall']['trades'] += 1
        stats['overall']['total_pnl'] += trade.pnl
        stats['overall']['durations'].append(trade.duration)
        
        if trade.is_winner:
            stats['overall']['wins'] += 1
            stats['overall']['winning_pnl'] += trade.pnl
            stats['overall']['largest_win'] = max(
                stats['overall']['largest_win'], trade.pnl
            )
        else:
            stats['overall']['losses'] += 1
            stats['overall']['losing_pnl'] += trade.pnl
            stats['overall']['largest_loss'] = min(
                stats['overall']['largest_loss'], trade.pnl
            )
        
        # Entry regime statistics
        entry_regime = trade.entry_regime.lower()
        self._update_regime_stats(entry_regime, trade, stats['by_entry_regime'])
        
        # Exit regime statistics
        exit_regime = trade.exit_regime.lower()
        self._update_regime_stats(exit_regime, trade, stats['by_exit_regime'])
        
        # Regime transition statistics
        transition = f"{entry_regime}→{exit_regime}"
        self._update_regime_stats(transition, trade, stats['by_regime_transition'])
    
    def _update_regime_stats(self, regime: str, trade: Trade, stats_dict: Dict) -> None:
        """Update statistics for specific regime."""
        stats = stats_dict[regime]
        stats['trades'] += 1
        stats['total_pnl'] += trade.pnl
        stats['durations'].append(trade.duration)
        
        if trade.is_winner:
            stats['wins'] += 1
            stats['winning_pnl'] += trade.pnl
            stats['largest_win'] = max(stats['largest_win'], trade.pnl)
        else:
            stats['losses'] += 1
            stats['losing_pnl'] += trade.pnl
            stats['largest_loss'] = min(stats['largest_loss'], trade.pnl)
    
    def _calculate_derived_metrics(self, stats: Dict) -> None:
        """Calculate derived metrics like win rates, averages."""
        for category in ['overall', 'by_entry_regime', 'by_exit_regime', 'by_regime_transition']:
            if category == 'overall':
                self._calculate_category_metrics(stats['overall'])
            else:
                for regime, regime_stats in stats[category].items():
                    self._calculate_category_metrics(regime_stats)
    
    def _calculate_category_metrics(self, stats: Dict) -> None:
        """Calculate metrics for a category."""
        # Win rate
        if stats['trades'] > 0:
            stats['win_rate'] = stats['wins'] / stats['trades']
        else:
            stats['win_rate'] = 0.0
        
        # Average PnL
        if stats['trades'] > 0:
            stats['avg_pnl'] = stats['total_pnl'] / stats['trades']
        else:
            stats['avg_pnl'] = 0.0
        
        # Average win
        if stats['wins'] > 0:
            stats['avg_win'] = stats['winning_pnl'] / stats['wins']
        else:
            stats['avg_win'] = 0.0
        
        # Average loss
        if stats['losses'] > 0:
            stats['avg_loss'] = stats['losing_pnl'] / stats['losses']
        else:
            stats['avg_loss'] = 0.0
        
        # Average duration
        if stats['durations']:
            stats['avg_duration'] = sum(stats['durations']) / len(stats['durations'])
            stats['median_duration'] = sorted(stats['durations'])[len(stats['durations']) // 2]
        else:
            stats['avg_duration'] = 0.0
            stats['median_duration'] = 0.0
        
        # Profit factor
        if abs(stats['losing_pnl']) > 0:
            stats['profit_factor'] = stats['winning_pnl'] / abs(stats['losing_pnl'])
        else:
            stats['profit_factor'] = float('inf') if stats['winning_pnl'] > 0 else 0.0
        
        # Expectancy
        stats['expectancy'] = (stats['win_rate'] * stats['avg_win'] + 
                              (1 - stats['win_rate']) * stats['avg_loss'])
    
    def _create_empty_stats(self) -> Dict:
        """Create empty statistics structure."""
        return {
            'by_entry_regime': {},
            'by_exit_regime': {},
            'by_regime_transition': {},
            'overall': self._init_regime_stats()
        }
    
    def print_analysis(self, stats: Dict) -> None:
        """Print formatted regime analysis."""
        print("=" * 70)
        print("REGIME PERFORMANCE ANALYSIS")
        print("=" * 70)
        
        # Overall statistics
        overall = stats['overall']
        print(f"\n📊 OVERALL PERFORMANCE")
        print(f"   Trades: {overall['trades']}")
        print(f"   Win Rate: {overall['win_rate']:.1%}")
        print(f"   Total PnL: R{overall['total_pnl']:.2f}")
        print(f"   Avg PnL: R{overall['avg_pnl']:.2f}")
        print(f"   Profit Factor: {overall['profit_factor']:.2f}")
        print(f"   Expectancy: R{overall['expectancy']:.2f}")
        
        # By entry regime
        if stats['by_entry_regime']:
            print(f"\n🎭 PERFORMANCE BY ENTRY REGIME")
            for regime, regime_stats in sorted(stats['by_entry_regime'].items()):
                if regime_stats['trades'] > 0:
                    print(f"   {regime.upper():10s}: {regime_stats['trades']:2d} trades, "
                          f"Win: {regime_stats['win_rate']:.1%}, "
                          f"Avg PnL: R{regime_stats['avg_pnl']:+.2f}, "
                          f"PF: {regime_stats['profit_factor']:.2f}")
        
        # By exit regime
        if stats['by_exit_regime']:
            print(f"\n🚪 PERFORMANCE BY EXIT REGIME")
            for regime, regime_stats in sorted(stats['by_exit_regime'].items()):
                if regime_stats['trades'] > 0:
                    print(f"   {regime.upper():10s}: {regime_stats['trades']:2d} trades, "
                          f"Win: {regime_stats['win_rate']:.1%}, "
                          f"Avg PnL: R{regime_stats['avg_pnl']:+.2f}")
        
        # Best and worst performing entry regimes
        if stats['by_entry_regime']:
            print(f"\n🏆 BEST/WORST ENTRY REGIMES")
            
            # Filter regimes with enough trades
            valid_regimes = {k: v for k, v in stats['by_entry_regime'].items() 
                           if v['trades'] >= 3}
            
            if valid_regimes:
                best = max(valid_regimes.items(), 
                          key=lambda x: x[1]['avg_pnl'])
                worst = min(valid_regimes.items(), 
                           key=lambda x: x[1]['avg_pnl'])
                
                print(f"   Best:  {best[0].upper():10s} "
                      f"(Avg PnL: R{best[1]['avg_pnl']:+.2f}, "
                      f"Trades: {best[1]['trades']})")
                print(f"   Worst: {worst[0].upper():10s} "
                      f"(Avg PnL: R{worst[1]['avg_pnl']:+.2f}, "
                      f"Trades: {worst[1]['trades']})")
        
        # Regime transitions
        if stats['by_regime_transition']:
            print(f"\n🔄 REGIME TRANSITIONS")
            # Show most common transitions
            common_transitions = sorted(
                stats['by_regime_transition'].items(),
                key=lambda x: x[1]['trades'],
                reverse=True
            )[:5]
            
            for transition, transition_stats in common_transitions:
                if transition_stats['trades'] > 0:
                    print(f"   {transition:15s}: {transition_stats['trades']:2d} trades, "
                          f"Win: {transition_stats['win_rate']:.1%}, "
                          f"Avg PnL: R{transition_stats['avg_pnl']:+.2f}")


def main():
    """Test regime analysis with sample trades."""
    print("=" * 70)
    print("REGIME ANALYSIS TEST")
    print("=" * 70)
    
    from backtest.trade import create_trade
    from datetime import datetime
    
    # Create sample trades with different regimes
    trades = [
        create_trade("W1", datetime(2024, 1, 1), 42000, 'trend',
                    datetime(2024, 1, 2), 42500, 'trend', 'exit', 250),
        create_trade("L1", datetime(2024, 1, 3), 42500, 'trend',
                    datetime(2024, 1, 3), 41580, 'range', 'stop_loss', 250),
        create_trade("W2", datetime(2024, 1, 5), 41500, 'range',
                    datetime(2024, 1, 6), 42000, 'trend', 'exit', 250),
        create_trade("W3", datetime(2024, 1, 8), 42000, 'trend',
                    datetime(2024, 1, 9), 42400, 'trend', 'exit', 250),
        create_trade("L2", datetime(2024, 1, 10), 42400, 'trend',
                    datetime(2024, 1, 10), 41580, 'chaos', 'stop_loss', 250),
        create_trade("W4", datetime(2024, 1, 12), 41500, 'range',
                    datetime(2024, 1, 13), 41800, 'range', 'exit', 250),
    ]
    
    # Analyze
    analyzer = RegimeAnalyzer()
    stats = analyzer.analyze_trades(trades)
    
    # Print analysis
    analyzer.print_analysis(stats)
    
    print("\n" + "=" * 70)
    print("✅ Regime analysis test complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
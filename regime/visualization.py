"""
Regime visualization and analysis tools.

Provides functions for:
- Regime transition detection
- Regime duration analysis
- Transition matrices
- Visual plotting (optional)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import Counter


def detect_regime_transitions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect regime transitions in DataFrame.
    
    A transition occurs when regime changes from one period to next.
    
    Args:
        df: DataFrame with 'regime' column
        
    Returns:
        DataFrame with transition information added:
        - 'regime_changed': Boolean indicating transition
        - 'regime_previous': Previous regime
        - 'regime_duration': How long in current regime
        
    Raises:
        ValueError: If 'regime' column missing
    """
    if 'regime' not in df.columns:
        raise ValueError("DataFrame must contain 'regime' column")
    
    df = df.copy()
    
    # Detect changes
    df['regime_previous'] = df['regime'].shift(1)
    df['regime_changed'] = df['regime'] != df['regime_previous']
    
    # Calculate duration in current regime
    regime_groups = (df['regime_changed'].cumsum())
    df.loc[df.index[0], 'regime_changed'] = False
    
    df['regime_duration'] = df.groupby(regime_groups).cumcount() + 1

    return df


def get_regime_durations(df: pd.DataFrame) -> Dict[str, List[int]]:
    """
    Get duration statistics for each regime.
    
    Args:
        df: DataFrame with regime transitions detected
        
    Returns:
        Dictionary mapping regime to list of durations
    """
    if 'regime_duration' not in df.columns:
        df = detect_regime_transitions(df)
    
    durations = {}
    
    # Group by regime changes
    regime_groups = (df['regime_changed'].cumsum())
    
    for regime in df['regime'].unique():
        regime_df = df[df['regime'] == regime]
        regime_group_ids = regime_groups[regime_df.index]
        
        # Get max duration for each group (last value before change)
        group_durations = regime_df.groupby(regime_group_ids)['regime_duration'].max()
        
        durations[regime] = group_durations.tolist()
    
    return durations


def calculate_regime_duration_stats(durations: Dict[str, List[int]]) -> Dict[str, Dict]:
    """
    Calculate statistics for regime durations.
    
    Args:
        durations: Dictionary mapping regime to list of durations
        
    Returns:
        Dictionary with statistics for each regime
    """
    stats = {}
    
    for regime, duration_list in durations.items():
        if not duration_list:
            stats[regime] = {
                'count': 0,
                'mean': 0,
                'median': 0,
                'min': 0,
                'max': 0
            }
            continue
        
        stats[regime] = {
            'count': len(duration_list),
            'mean': np.mean(duration_list),
            'median': np.median(duration_list),
            'min': np.min(duration_list),
            'max': np.max(duration_list),
            'total_periods': sum(duration_list)
        }
    
    return stats


def create_transition_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create regime transition matrix.
    
    Shows probability of transitioning from one regime to another.
    
    Args:
        df: DataFrame with regime transitions detected
        
    Returns:
        DataFrame representing transition matrix
    """
    if 'regime_previous' not in df.columns:
        df = detect_regime_transitions(df)
    
    # Get transitions (exclude first row which has no previous)
    transitions = df[df['regime_changed'] & df['regime_previous'].notna()][
        ['regime_previous', 'regime']
    ]
    
    # Count transitions
    transition_counts = {}
    
    for regime_from in df['regime'].unique():
        transition_counts[regime_from] = {}
        
        for regime_to in df['regime'].unique():
            count = len(transitions[
                (transitions['regime_previous'] == regime_from) &
                (transitions['regime'] == regime_to)
            ])
            transition_counts[regime_from][regime_to] = count
    
    # Convert to DataFrame
    matrix = pd.DataFrame(transition_counts).T
    
    # Calculate probabilities (normalize by row)
    matrix_prob = matrix.div(matrix.sum(axis=1), axis=0)
    
    return matrix_prob


def get_regime_persistence(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate regime persistence (probability of staying in same regime).
    
    Args:
        df: DataFrame with regime column
        
    Returns:
        Dictionary mapping regime to persistence probability
    """
    if 'regime_previous' not in df.columns:
        df = detect_regime_transitions(df)
    
    persistence = {}
    
    for regime in df['regime'].unique():
        regime_df = df[df['regime'] == regime]
        
        if len(regime_df) == 0:
            persistence[regime] = 0.0
            continue
        
        # Count periods where regime didn't change
        stayed = (~regime_df['regime_changed']).sum()
        total = len(regime_df)
        
        persistence[regime] = stayed / total if total > 0 else 0.0
    
    return persistence


def analyze_regime_sequence(df: pd.DataFrame) -> Dict:
    """
    Comprehensive regime sequence analysis.
    
    Args:
        df: DataFrame with regime classifications
        
    Returns:
        Dictionary with complete analysis
    """
    # Detect transitions
    df = detect_regime_transitions(df)
    
    # Get durations
    durations = get_regime_durations(df)
    duration_stats = calculate_regime_duration_stats(durations)
    
    # Get transition matrix
    transition_matrix = create_transition_matrix(df)
    
    # Get persistence
    persistence = get_regime_persistence(df)
    
    # Count total transitions
    total_transitions = df['regime_changed'].sum()
    
    analysis = {
        'total_periods': len(df),
        'total_transitions': int(total_transitions),
        'transition_rate': total_transitions / len(df) if len(df) > 0 else 0,
        'durations': durations,
        'duration_stats': duration_stats,
        'transition_matrix': transition_matrix,
        'persistence': persistence
    }
    
    return analysis


def print_regime_analysis(analysis: Dict) -> None:
    """
    Print formatted regime analysis.
    
    Args:
        analysis: Analysis dictionary from analyze_regime_sequence
    """
    print("=" * 60)
    print("REGIME SEQUENCE ANALYSIS")
    print("=" * 60)
    
    print(f"\nTotal periods: {analysis['total_periods']}")
    print(f"Total transitions: {analysis['total_transitions']}")
    print(f"Transition rate: {analysis['transition_rate']:.1%}")
    
    print("\n" + "-" * 60)
    print("REGIME DURATION STATISTICS")
    print("-" * 60)
    
    for regime, stats in analysis['duration_stats'].items():
        print(f"\n{regime.upper()}:")
        print(f"  Occurrences: {stats['count']}")
        print(f"  Mean duration: {stats['mean']:.1f} periods")
        print(f"  Median duration: {stats['median']:.1f} periods")
        print(f"  Range: {stats['min']}-{stats['max']} periods")
        if 'total_periods' in stats:
            print(f"  Total time: {stats['total_periods']} periods")
    
    print("\n" + "-" * 60)
    print("REGIME PERSISTENCE")
    print("-" * 60)
    
    for regime, pers in analysis['persistence'].items():
        print(f"{regime:10s}: {pers:.1%} (probability of staying)")
    
    print("\n" + "-" * 60)
    print("TRANSITION MATRIX (Probabilities)")
    print("-" * 60)
    print("From \\ To:", end="")
    
    # Print transition matrix
    matrix = analysis['transition_matrix']
    
    # Header
    for col in matrix.columns:
        print(f" {col:8s}", end="")
    print()
    
    # Rows
    for idx in matrix.index:
        print(f"{idx:10s}:", end="")
        for col in matrix.columns:
            val = matrix.loc[idx, col]
            if pd.notna(val):
                print(f" {val:7.1%}", end="")
            else:
                print(f" {'N/A':7s}", end="")
        print()


def create_regime_timeline_text(
    df: pd.DataFrame,
    max_width: int = 60
) -> str:
    """
    Create text-based timeline visualization of regimes.
    
    Args:
        df: DataFrame with regime classifications
        max_width: Maximum width of timeline
        
    Returns:
        String representation of timeline
    """
    if len(df) == 0:
        return "No data to visualize"
    
    # Detect transitions
    df = detect_regime_transitions(df)
    
    # Regime symbols
    symbols = {
        'trend': '↗',
        'range': '→',
        'chaos': '⚡',
        'no_trade': '✖'
    }
    
    # Sample data to fit width
    if len(df) > max_width:
        sample_indices = np.linspace(0, len(df) - 1, max_width, dtype=int)
        df_sample = df.iloc[sample_indices]
    else:
        df_sample = df
    
    # Create timeline
    timeline = []
    for _, row in df_sample.iterrows():
        symbol = symbols.get(row['regime'], '?')
        timeline.append(symbol)
    
    timeline_str = ''.join(timeline)
    
    # Add legend
    legend = "\nLegend: ↗=Trend  →=Range  ⚡=Chaos  ✖=No-Trade"
    
    return timeline_str + legend


def main():
    """Test visualization with synthetic data."""
    print("=" * 60)
    print("REGIME VISUALIZATION TEST")
    print("=" * 60)
    
    # Create sample regime sequence
    regimes = (
        ['trend'] * 20 +
        ['range'] * 15 +
        ['trend'] * 25 +
        ['chaos'] * 10 +
        ['range'] * 20 +
        ['no_trade'] * 5 +
        ['trend'] * 15
    )
    
    df = pd.DataFrame({
        'regime': regimes,
        'close': 42000 + np.random.randn(len(regimes)) * 500
    })
    
    # Analyze
    analysis = analyze_regime_sequence(df)
    
    # Print analysis
    print_regime_analysis(analysis)
    
    # Print timeline
    print("\n" + "=" * 60)
    print("REGIME TIMELINE")
    print("=" * 60)
    print(create_regime_timeline_text(df))
    
    print("\n" + "=" * 60)
    print("✅ Visualization test complete")


if __name__ == "__main__":
    main()
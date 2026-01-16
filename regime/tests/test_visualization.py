"""
Tests for regime visualization and analysis.
"""

import pytest
import pandas as pd
import numpy as np
from regime.visualization import (
    detect_regime_transitions,
    get_regime_durations,
    calculate_regime_duration_stats,
    create_transition_matrix,
    get_regime_persistence,
    analyze_regime_sequence,
    create_regime_timeline_text
)


def test_detect_regime_transitions():
    """Test regime transition detection."""
    df = pd.DataFrame({
        'regime': ['trend', 'trend', 'range', 'range', 'trend']
    })
    
    df_trans = detect_regime_transitions(df)
    
    # Check columns added
    assert 'regime_changed' in df_trans.columns
    assert 'regime_previous' in df_trans.columns
    assert 'regime_duration' in df_trans.columns
    
    # Check transitions detected correctly
    # First row has no previous (NaN)
    assert pd.isna(df_trans['regime_previous'].iloc[0])
    
    # Second row: same regime (no change)
    assert df_trans['regime_changed'].iloc[1] == False
    
    # Third row: change from trend to range
    assert df_trans['regime_changed'].iloc[2] == True


def test_regime_duration_calculation():
    """Test regime duration calculation."""
    df = pd.DataFrame({
        'regime': ['trend', 'trend', 'trend', 'range', 'range', 'trend']
    })
    
    df_trans = detect_regime_transitions(df)
    
    # Check durations
    # First trend: should count up to 3
    assert df_trans['regime_duration'].iloc[0] == 1
    assert df_trans['regime_duration'].iloc[1] == 2
    assert df_trans['regime_duration'].iloc[2] == 3
    
    # Range: should reset to 1, then 2
    assert df_trans['regime_duration'].iloc[3] == 1
    assert df_trans['regime_duration'].iloc[4] == 2
    
    # Second trend: should reset to 1
    assert df_trans['regime_duration'].iloc[5] == 1


def test_get_regime_durations():
    """Test getting regime duration lists."""
    df = pd.DataFrame({
        'regime': ['trend'] * 5 + ['range'] * 3 + ['trend'] * 2
    })
    
    durations = get_regime_durations(df)
    
    # Should have entries for both regimes
    assert 'trend' in durations
    assert 'range' in durations
    
    # Trend appeared twice (5 periods, then 2 periods)
    assert len(durations['trend']) == 2
    assert 5 in durations['trend']
    assert 2 in durations['trend']
    
    # Range appeared once (3 periods)
    assert len(durations['range']) == 1
    assert 3 in durations['range']


def test_calculate_regime_duration_stats():
    """Test duration statistics calculation."""
    durations = {
        'trend': [5, 3, 7, 2],
        'range': [10, 8]
    }
    
    stats = calculate_regime_duration_stats(durations)
    
    # Check trend stats
    assert stats['trend']['count'] == 4
    assert stats['trend']['mean'] == 4.25  # (5+3+7+2)/4
    assert stats['trend']['min'] == 2
    assert stats['trend']['max'] == 7
    
    # Check range stats
    assert stats['range']['count'] == 2
    assert stats['range']['mean'] == 9.0  # (10+8)/2


def test_create_transition_matrix():
    """Test transition matrix creation."""
    df = pd.DataFrame({
        'regime': ['trend', 'trend', 'range', 'trend', 'range', 'range']
    })
    
    matrix = create_transition_matrix(df)
    
    # Check matrix structure
    assert 'trend' in matrix.index
    assert 'range' in matrix.index
    assert 'trend' in matrix.columns
    assert 'range' in matrix.columns
    
    # Check probabilities sum to 1 (or close to it)
    for idx in matrix.index:
        row_sum = matrix.loc[idx].sum()
        # Allow some rows to be 0 if regime never transitions
        assert row_sum == 0 or np.isclose(row_sum, 1.0)


def test_get_regime_persistence():
    """Test regime persistence calculation."""
    df = pd.DataFrame({
        'regime': ['trend', 'trend', 'trend', 'range', 'trend']
    })
    
    persistence = get_regime_persistence(df)
    
    # Trend appeared 4 times, stayed same 2 times (indices 1, 2)
    # Persistence = 2/4 = 0.5
    assert 'trend' in persistence
    assert 0 <= persistence['trend'] <= 1


def test_analyze_regime_sequence():
    """Test complete regime sequence analysis."""
    df = pd.DataFrame({
        'regime': ['trend'] * 10 + ['range'] * 5 + ['chaos'] * 3
    })
    
    analysis = analyze_regime_sequence(df)
    
    # Check all expected keys
    assert 'total_periods' in analysis
    assert 'total_transitions' in analysis
    assert 'durations' in analysis
    assert 'duration_stats' in analysis
    assert 'transition_matrix' in analysis
    assert 'persistence' in analysis
    
    # Check values
    assert analysis['total_periods'] == 18
    assert analysis['total_transitions'] == 2  # trend→range, range→chaos


def test_create_regime_timeline_text():
    """Test text timeline creation."""
    df = pd.DataFrame({
        'regime': ['trend', 'range', 'chaos', 'no_trade']
    })
    
    timeline = create_regime_timeline_text(df)
    
    # Should contain symbols
    assert '↗' in timeline  # trend
    assert '→' in timeline  # range
    assert '⚡' in timeline  # chaos
    assert '✖' in timeline  # no_trade
    
    # Should contain legend
    assert 'Legend' in timeline


def test_timeline_with_long_data():
    """Test timeline handles long data by sampling."""
    df = pd.DataFrame({
        'regime': ['trend'] * 200
    })
    
    timeline = create_regime_timeline_text(df, max_width=60)
    
    # Timeline should be approximately max_width
    # (minus legend)
    lines = timeline.split('\n')
    assert len(lines[0]) <= 65  # Allow some margin


def test_detect_transitions_missing_regime():
    """Test error handling for missing regime column."""
    df = pd.DataFrame({
        'close': [100, 101, 102]
    })
    
    with pytest.raises(ValueError, match="regime"):
        detect_regime_transitions(df)


def test_empty_dataframe_handling():
    """Test handling of empty DataFrame."""
    df = pd.DataFrame({'regime': []})
    
    timeline = create_regime_timeline_text(df)
    assert "No data" in timeline


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
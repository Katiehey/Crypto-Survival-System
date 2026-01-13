"""
Tests for Efficiency Ratio calculations.
"""

import pytest
import numpy as np
import pandas as pd
from regime.features import (
    calculate_efficiency_ratio,
    calculate_efficiency_percentile,
    smooth_efficiency_ratio,
    classify_trend_strength,
    add_efficiency_features,
    validate_efficiency
)


def test_efficiency_ratio_perfect_trend():
    """Test efficiency ratio with perfect trend (straight line)."""
    # Perfect uptrend: 100 -> 110 (no noise)
    close = pd.Series([100, 102, 104, 106, 108, 110])
    
    er = calculate_efficiency_ratio(close, period=5)
    
    # Should be 1.0 (perfect efficiency) for last value
    # Net change = 10, Total movement = 2+2+2+2+2 = 10
    assert np.isclose(er.iloc[-1], 1.0, atol=0.01)


def test_efficiency_ratio_no_trend():
    """Test efficiency ratio with no net movement."""
    # Price oscillates: 100 -> 110 -> 100 (no net change)
    close = pd.Series([100, 105, 110, 105, 100])
    
    er = calculate_efficiency_ratio(close, period=4)
    
    # Should be 0.0 (no efficiency) for last value
    # Net change = 0, Total movement > 0
    assert np.isclose(er.iloc[-1], 0.0, atol=0.01)


def test_efficiency_ratio_range():
    """Test that efficiency ratio stays in [0, 1] range."""
    # Random walk
    np.random.seed(42)
    close = pd.Series(100 + np.cumsum(np.random.randn(100)))
    
    er = calculate_efficiency_ratio(close, period=10)
    
    valid_values = er.dropna()
    
    # All values should be between 0 and 1
    assert (valid_values >= 0).all()
    assert (valid_values <= 1).all()


def test_efficiency_ratio_period_validation():
    """Test period validation."""
    close = pd.Series([100, 101, 102])
    
    with pytest.raises(ValueError):
        calculate_efficiency_ratio(close, period=1)
    
    with pytest.raises(ValueError):
        calculate_efficiency_ratio(close, period=0)


def test_efficiency_ratio_with_flat_price():
    """Test efficiency ratio when price is completely flat."""
    # Flat price (no movement at all)
    close = pd.Series([100.0] * 20)
    
    er = calculate_efficiency_ratio(close, period=10)
    
    # Should handle division by zero gracefully (return NaN)
    # Net change = 0, Total movement = 0
    assert pd.isna(er.iloc[-1])


def test_efficiency_percentile():
    """Test efficiency percentile calculation."""
    # Create series where last value is high efficiency
    efficiency = pd.Series([0.1] * 50 + [0.9] * 50 + [0.95])
    
    percentile = calculate_efficiency_percentile(efficiency, lookback=100)
    
    # Last value should be high percentile
    last_percentile = percentile.iloc[-1]
    assert last_percentile > 90


def test_efficiency_percentile_lookback_validation():
    """Test percentile lookback validation."""
    efficiency = pd.Series([0.5, 0.6, 0.7])
    
    with pytest.raises(ValueError):
        calculate_efficiency_percentile(efficiency, lookback=1)


def test_smooth_efficiency_ratio():
    """Test efficiency ratio smoothing."""
    # Noisy efficiency values
    efficiency = pd.Series([0.5, 0.8, 0.4, 0.9, 0.3, 0.7])
    
    smoothed = smooth_efficiency_ratio(efficiency, smoothing_period=3)
    
    # Smoothed values should be less volatile
    smoothed_valid = smoothed.dropna()
    
    assert len(smoothed_valid) > 0
    assert not smoothed_valid.empty


def test_smooth_efficiency_period_validation():
    """Test smoothing period validation."""
    efficiency = pd.Series([0.5, 0.6, 0.7])
    
    with pytest.raises(ValueError):
        smooth_efficiency_ratio(efficiency, smoothing_period=0)


def test_classify_trend_strength():
    """Test trend strength classification."""
    efficiency = pd.Series([0.9, 0.5, 0.3, 0.1])
    
    strength = classify_trend_strength(efficiency)
    
    assert strength.iloc[0] == 'strong_trend'
    assert strength.iloc[1] == 'moderate_trend'
    assert strength.iloc[2] == 'weak_trend'
    assert strength.iloc[3] == 'no_trend'


def test_classify_trend_strength_nan():
    """Test trend strength classification with NaN."""
    efficiency = pd.Series([0.5, np.nan, 0.3])
    
    strength = classify_trend_strength(efficiency)
    
    assert strength.iloc[1] == 'unknown'


def test_add_efficiency_features():
    """Test adding all efficiency features."""
    df = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(50))
    })
    
    df_features = add_efficiency_features(df)
    
    # Check all columns added
    assert 'efficiency_ratio' in df_features.columns
    assert 'efficiency_ratio_smooth' in df_features.columns
    assert 'efficiency_percentile' in df_features.columns
    assert 'trend_strength' in df_features.columns


def test_add_efficiency_features_missing_close():
    """Test error handling for missing close column."""
    df = pd.DataFrame({
        'open': [100, 101, 102]
    })
    
    with pytest.raises(ValueError, match="close"):
        add_efficiency_features(df)


def test_validate_efficiency_success():
    """Test efficiency validation with valid data."""
    df = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(50))
    })
    
    df = add_efficiency_features(df)
    
    is_valid, message = validate_efficiency(df)
    
    assert is_valid
    assert "passed" in message.lower()


def test_validate_efficiency_out_of_range():
    """Test efficiency validation catches out-of-range values."""
    df = pd.DataFrame({
        'efficiency_ratio': [0.5, 1.5, 0.7]  # 1.5 is invalid
    })
    
    is_valid, message = validate_efficiency(df)
    
    assert not is_valid
    assert "range" in message.lower()


def test_validate_efficiency_infinite():
    """Test efficiency validation catches infinite values."""
    df = pd.DataFrame({
        'efficiency_ratio': [0.5, np.inf, 0.7]
    })
    
    is_valid, message = validate_efficiency(df)
    
    assert not is_valid
    assert "infinite" in message.lower()


def test_efficiency_with_trending_data():
    """Test efficiency correctly identifies trending data."""
    # Strong uptrend
    close = pd.Series(range(100, 200))  # Linear uptrend
    
    er = calculate_efficiency_ratio(close, period=10)
    
    # Should have high efficiency (close to 1.0)
    mean_er = er.dropna().mean()
    assert mean_er > 0.8


def test_efficiency_with_ranging_data():
    """Test efficiency correctly identifies ranging data."""
    # Oscillating price (no trend)
    close = pd.Series([100 + 10 * np.sin(i * 0.5) for i in range(100)])
    
    er = calculate_efficiency_ratio(close, period=20)
    
    # Should have low efficiency
    mean_er = er.dropna().mean()
    assert mean_er < 0.3


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
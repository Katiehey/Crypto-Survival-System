"""
Tests for ATR calculations.

These tests use known input values to validate mathematical correctness.
"""

import pytest
import numpy as np
import pandas as pd
from regime.features import (
    calculate_true_range,
    calculate_atr,
    calculate_atr_percentile,
    normalize_atr,
    add_atr_features,
    validate_atr
)


def test_true_range_basic():
    """Test True Range with simple known values."""
    high = pd.Series([10, 12, 11, 13])
    low = pd.Series([9, 10, 9, 11])
    close = pd.Series([9.5, 11, 10, 12])
    
    tr = calculate_true_range(high, low, close)
    
    # First value: high-low only (no previous close)
    assert tr.iloc[0] == 1.0  # 10 - 9
    
    # Second value: max of (12-10, |12-9.5|, |10-9.5|)
    # = max(2, 2.5, 0.5) = 2.5
    assert tr.iloc[1] == 2.5
    
    # Third value: max of (11-9, |11-11|, |9-11|)
    # = max(2, 0, 2) = 2
    assert tr.iloc[2] == 2.0


def test_true_range_with_gap():
    """Test True Range with price gap."""
    high = pd.Series([100, 105, 110])
    low = pd.Series([95, 100, 95])  # Gap down
    close = pd.Series([98, 103, 97])
    
    tr = calculate_true_range(high, low, close)
    
    # Third candle has gap down from 103 to 110/95
    # TR = max(110-95, |110-103|, |95-103|) = max(15, 7, 8) = 15
    assert tr.iloc[2] == 15.0


def test_atr_basic():
    """Test ATR calculation."""
    high = pd.Series([10, 12, 11, 13, 12] * 5)  # 25 values
    low = pd.Series([9, 10, 9, 11, 10] * 5)
    close = pd.Series([9.5, 11, 10, 12, 11] * 5)
    
    atr = calculate_atr(high, low, close, period=5)
    
    # First few values should be NaN (insufficient data)
    assert pd.isna(atr.iloc[0])
    assert not pd.isna(atr.iloc[4])  # Need 'period' values
    
    # Later values should be valid
    assert not pd.isna(atr.iloc[10])
    
    # ATR should be positive
    assert (atr.dropna() > 0).all()


def test_atr_increases_with_volatility():
    """Test that ATR increases when volatility increases."""
    # Low volatility period
    high_low = pd.Series([10.1] * 20)
    low_low = pd.Series([10.0] * 20)
    close_low = pd.Series([10.05] * 20)
    
    # High volatility period
    high_high = pd.Series([12.0] * 20)
    low_high = pd.Series([10.0] * 20)
    close_high = pd.Series([11.0] * 20)
    
    atr_low = calculate_atr(high_low, low_low, close_low, period=5)
    atr_high = calculate_atr(high_high, low_high, close_high, period=5)
    
    # High volatility should have higher ATR
    assert atr_high.iloc[-1] > atr_low.iloc[-1]


def test_atr_period_validation():
    """Test ATR period validation."""
    high = pd.Series([10, 11, 12])
    low = pd.Series([9, 10, 11])
    close = pd.Series([9.5, 10.5, 11.5])
    
    # Period must be >= 1
    with pytest.raises(ValueError):
        calculate_atr(high, low, close, period=0)
    
    with pytest.raises(ValueError):
        calculate_atr(high, low, close, period=-1)


def test_atr_percentile():
    """Test ATR percentile calculation."""
    # Create ATR series where last value is at 80th percentile
    atr = pd.Series([1.0] * 20 + [5.0] * 80 + [8.0])  # 101 values
    
    percentile = calculate_atr_percentile(atr, lookback=100)
    
    # Last value should be high percentile
    last_percentile = percentile.iloc[-1]
    assert last_percentile > 80  # Should be around 80th percentile


def test_atr_percentile_lookback_validation():
    """Test percentile lookback validation."""
    atr = pd.Series([1.0, 2.0, 3.0])
    
    with pytest.raises(ValueError):
        calculate_atr_percentile(atr, lookback=1)
    
    with pytest.raises(ValueError):
        calculate_atr_percentile(atr, lookback=0)


def test_normalize_atr():
    """Test ATR normalization."""
    atr = pd.Series([100.0, 200.0, 300.0])
    close = pd.Series([10000.0, 20000.0, 30000.0])
    
    normalized = normalize_atr(atr, close)
    
    # Should all be 1% (0.01)
    assert np.allclose(normalized, 0.01)


def test_normalize_atr_zero_price():
    """Test ATR normalization handles zero prices."""
    atr = pd.Series([100.0, 200.0])
    close = pd.Series([10000.0, 0.0])  # Zero price
    
    normalized = normalize_atr(atr, close)
    
    # First value should be normal
    assert not pd.isna(normalized.iloc[0])
    
    # Second value should be NaN (division by zero)
    assert pd.isna(normalized.iloc[1])


def test_add_atr_features():
    """Test adding all ATR features to DataFrame."""
    df = pd.DataFrame({
        'high': [10, 12, 11, 13, 12] * 20,
        'low': [9, 10, 9, 11, 10] * 20,
        'close': [9.5, 11, 10, 12, 11] * 20,
    })
    
    df_features = add_atr_features(df)
    
    # Check all expected columns added
    assert 'tr' in df_features.columns
    assert 'atr' in df_features.columns
    assert 'atr_pct' in df_features.columns
    assert 'atr_percentile' in df_features.columns
    
    # Check values are valid
    assert not df_features['tr'].dropna().empty
    assert not df_features['atr'].dropna().empty


def test_add_atr_features_missing_columns():
    """Test error handling for missing columns."""
    df = pd.DataFrame({
        'high': [10, 11, 12],
        # Missing 'low' and 'close'
    })
    
    with pytest.raises(ValueError, match="Missing required columns"):
        add_atr_features(df)


def test_validate_atr_success():
    """Test ATR validation with valid data."""
    df = pd.DataFrame({
        'high': [100, 102, 101] * 20,
        'low': [99, 100, 99] * 20,
        'close': [99.5, 101, 100] * 20,
    })
    
    df = add_atr_features(df)
    
    is_valid, message = validate_atr(df)
    
    assert is_valid
    assert "passed" in message.lower()


def test_validate_atr_negative():
    """Test ATR validation catches negative values."""
    df = pd.DataFrame({
        'atr': [1.0, 2.0, -1.0, 3.0]
    })
    
    is_valid, message = validate_atr(df)
    
    assert not is_valid
    assert "negative" in message.lower()


def test_validate_atr_infinite():
    """Test ATR validation catches infinite values."""
    df = pd.DataFrame({
        'atr': [1.0, 2.0, np.inf, 3.0]
    })
    
    is_valid, message = validate_atr(df)
    
    assert not is_valid
    assert "infinite" in message.lower()


def test_validate_atr_percentile_range():
    """Test ATR validation catches invalid percentiles."""
    df = pd.DataFrame({
        'atr': [1.0, 2.0, 3.0],
        'atr_percentile': [50.0, 150.0, 60.0]  # 150 is invalid
    })
    
    is_valid, message = validate_atr(df)
    
    assert not is_valid
    assert "percentile" in message.lower()


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
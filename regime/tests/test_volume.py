"""
Tests for volume metrics calculations.
"""

import pytest
import numpy as np
import pandas as pd
from regime.features import (
    calculate_volume_ma,
    calculate_volume_ratio,
    calculate_volume_percentile,
    classify_volume_regime,
    detect_volume_spike,
    add_volume_features,
    validate_volume
)


def test_volume_ma():
    """Test volume moving average calculation."""
    volume = pd.Series([100, 110, 120, 130, 140])
    
    volume_ma = calculate_volume_ma(volume, period=3)
    
    # First two should be NaN
    assert pd.isna(volume_ma.iloc[0])
    assert pd.isna(volume_ma.iloc[1])
    
    # Third should be average of first 3
    assert volume_ma.iloc[2] == (100 + 110 + 120) / 3


def test_volume_ma_period_validation():
    """Test volume MA period validation."""
    volume = pd.Series([100, 110, 120])
    
    with pytest.raises(ValueError):
        calculate_volume_ma(volume, period=0)


def test_volume_ratio():
    """Test volume ratio calculation."""
    volume = pd.Series([100, 200, 50])
    volume_ma = pd.Series([100, 100, 100])
    
    ratio = calculate_volume_ratio(volume, volume_ma)
    
    assert ratio.iloc[0] == 1.0  # 100/100
    assert ratio.iloc[1] == 2.0  # 200/100
    assert ratio.iloc[2] == 0.5  # 50/100


def test_volume_ratio_zero_ma():
    """Test volume ratio handles zero MA gracefully."""
    volume = pd.Series([100, 200])
    volume_ma = pd.Series([100, 0])  # Zero MA
    
    ratio = calculate_volume_ratio(volume, volume_ma)
    
    # First should be normal
    assert ratio.iloc[0] == 1.0
    
    # Second should be NaN (division by zero)
    assert pd.isna(ratio.iloc[1])


def test_volume_percentile():
    """Test volume percentile calculation."""
    # Create volume series where last value is high
    volume = pd.Series([100.0] * 50 + [500.0])
    
    percentile = calculate_volume_percentile(volume, lookback=50)
    
    # Last value should be 100th percentile
    last_percentile = percentile.iloc[-1]
    assert last_percentile == 100.0


def test_volume_percentile_lookback_validation():
    """Test percentile lookback validation."""
    volume = pd.Series([100, 110, 120])
    
    with pytest.raises(ValueError):
        calculate_volume_percentile(volume, lookback=1)


def test_classify_volume_regime():
    """Test volume regime classification."""
    volume_ratio = pd.Series([0.3, 0.8, 1.7, 2.5])
    
    regime = classify_volume_regime(volume_ratio)
    
    assert regime.iloc[0] == 'low'
    assert regime.iloc[1] == 'normal'
    assert regime.iloc[2] == 'high'
    assert regime.iloc[3] == 'very_high'


def test_classify_volume_regime_nan():
    """Test volume regime classification with NaN."""
    volume_ratio = pd.Series([1.0, np.nan, 0.5])
    
    regime = classify_volume_regime(volume_ratio)
    
    assert regime.iloc[1] == 'unknown'


def test_detect_volume_spike():
    """Test volume spike detection."""
    volume_ratio = pd.Series([1.0, 1.5, 2.5, 1.2])
    
    spikes = detect_volume_spike(volume_ratio, threshold=2.0)
    
    assert spikes.iloc[0] == False
    assert spikes.iloc[1] == False
    assert spikes.iloc[2] == True  # 2.5 >= 2.0
    assert spikes.iloc[3] == False


def test_detect_volume_spike_custom_threshold():
    """Test volume spike detection with custom threshold."""
    volume_ratio = pd.Series([1.0, 1.8, 2.0])
    
    spikes = detect_volume_spike(volume_ratio, threshold=1.5)
    
    assert spikes.iloc[0] == False
    assert spikes.iloc[1] == True
    assert spikes.iloc[2] == True


def test_add_volume_features():
    """Test adding all volume features."""
    df = pd.DataFrame({
        'volume': [100, 110, 120, 130, 140] * 20
    })
    
    df_features = add_volume_features(df)
    
    # Check all columns added
    assert 'volume_ma' in df_features.columns
    assert 'volume_ratio' in df_features.columns
    assert 'volume_percentile' in df_features.columns
    assert 'volume_regime' in df_features.columns
    assert 'volume_spike' in df_features.columns


def test_add_volume_features_missing_column():
    """Test error handling for missing volume column."""
    df = pd.DataFrame({
        'close': [100, 101, 102]
    })
    
    with pytest.raises(ValueError, match="volume"):
        add_volume_features(df)


def test_validate_volume_success():
    """Test volume validation with valid data."""
    df = pd.DataFrame({
        'volume': [100, 110, 120] * 20
    })
    
    df = add_volume_features(df)
    
    is_valid, message = validate_volume(df)
    
    assert is_valid
    assert "passed" in message.lower()


def test_validate_volume_negative():
    """Test volume validation catches negative values."""
    df = pd.DataFrame({
        'volume': [100, -50, 120]
    })
    
    is_valid, message = validate_volume(df)
    
    assert not is_valid
    assert "negative" in message.lower()


def test_validate_volume_infinite():
    """Test volume validation catches infinite values."""
    df = pd.DataFrame({
        'volume': [100, np.inf, 120]
    })
    
    is_valid, message = validate_volume(df)
    
    assert not is_valid
    assert "infinite" in message.lower()


def test_validate_volume_extreme_ratio():
    """Test volume validation catches extreme ratios."""
    df = pd.DataFrame({
        'volume': [100, 110, 120],
        'volume_ratio': [1.0, 15.0, 1.0]  # 15x is extreme
    })
    
    is_valid, message = validate_volume(df)
    
    assert not is_valid
    assert "ratio" in message.lower()


def test_volume_with_spike():
    """Test volume features correctly identify spike."""
    # Normal volume with one spike
    volume = pd.Series([100.0] * 50 + [300.0] + [100.0] * 49)
    
    df = pd.DataFrame({'volume': volume})
    df = add_volume_features(df)
    
    # Spike should be detected around position 50
    spike_count = df['volume_spike'].sum()
    assert spike_count >= 1


def test_volume_all_constant():
    """Test volume features with constant volume."""
    # Perfectly constant volume
    volume = pd.Series([100.0] * 100)
    
    df = pd.DataFrame({'volume': volume})
    df = add_volume_features(df)
    
    # All ratios should be 1.0 (or NaN for insufficient data)
    ratios = df['volume_ratio'].dropna()
    assert np.allclose(ratios, 1.0)


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
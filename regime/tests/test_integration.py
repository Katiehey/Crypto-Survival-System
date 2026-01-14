"""
Integration tests for complete feature pipeline.
"""

import pytest
import numpy as np
import pandas as pd
from regime.features import (
    calculate_all_features,
    validate_all_features,
    get_feature_summary,
    export_features_csv
)
import os


def test_calculate_all_features():
    """Test complete feature calculation pipeline."""
    # Create sample OHLCV data
    n = 100
    df = pd.DataFrame({
        'high': 42000 + np.random.randn(n) * 500,
        'low': 41000 + np.random.randn(n) * 500,
        'close': 41500 + np.random.randn(n) * 500,
        'volume': 100 + np.random.randn(n) * 20
    })
    df['volume'] = df['volume'].abs()  # Ensure positive
    
    # Calculate all features
    df_features = calculate_all_features(df)
    
    # Check all feature columns exist
    expected_features = [
        'tr', 'atr', 'atr_pct', 'atr_percentile',
        'efficiency_ratio', 'efficiency_ratio_smooth', 'efficiency_percentile', 'trend_strength',
        'volume_ma', 'volume_ratio', 'volume_percentile', 'volume_regime', 'volume_spike'
    ]
    
    for feature in expected_features:
        assert feature in df_features.columns, f"Missing feature: {feature}"


def test_calculate_all_features_missing_columns():
    """Test error handling for missing columns."""
    df = pd.DataFrame({
        'close': [100, 101, 102]
        # Missing high, low, volume
    })
    
    with pytest.raises(ValueError, match="Missing required columns"):
        calculate_all_features(df)


def test_validate_all_features():
    """Test complete feature validation."""
    # Create valid data
    n = 100
    df = pd.DataFrame({
        'high': 42000 + np.random.randn(n) * 500,
        'low': 41000 + np.random.randn(n) * 500,
        'close': 41500 + np.random.randn(n) * 500,
        'volume': 100 + np.abs(np.random.randn(n) * 20)
    })
    
    df = calculate_all_features(df)
    
    all_valid, results = validate_all_features(df)
    
    # All should be valid
    assert all_valid
    assert results['atr']['valid']
    assert results['efficiency']['valid']
    assert results['volume']['valid']


def test_get_feature_summary():
    """Test feature summary generation."""
    n = 100
    df = pd.DataFrame({
        'high': 42000 + np.random.randn(n) * 500,
        'low': 41000 + np.random.randn(n) * 500,
        'close': 41500 + np.random.randn(n) * 500,
        'volume': 100 + np.abs(np.random.randn(n) * 20)
    })
    
    df = calculate_all_features(df)
    
    summary = get_feature_summary(df)
    
    # Check summary structure
    assert 'atr' in summary
    assert 'efficiency' in summary
    assert 'volume' in summary
    
    # Check ATR summary
    assert 'mean' in summary['atr']
    assert 'current' in summary['atr']
    
    # Check efficiency summary
    assert 'mean' in summary['efficiency']
    assert 'current_strength' in summary['efficiency']
    
    # Check volume summary
    assert 'mean' in summary['volume']
    assert 'current_regime' in summary['volume']


def test_export_features_csv(tmp_path):
    """Test feature export to CSV."""
    # Create sample data with features
    n = 50
    df = pd.DataFrame({
        'timestamp': range(n),
        'high': 42000 + np.random.randn(n) * 500,
        'low': 41000 + np.random.randn(n) * 500,
        'close': 41500 + np.random.randn(n) * 500,
        'volume': 100 + np.abs(np.random.randn(n) * 20)
    })
    
    df = calculate_all_features(df)
    
    # Export
    export_path = tmp_path / "features_test.csv"
    export_features_csv(df, str(export_path))
    
    # Verify file exists
    assert export_path.exists()
    
    # Verify can be read back
    df_loaded = pd.read_csv(export_path)
    assert len(df_loaded) == len(df)
    assert 'atr' in df_loaded.columns
    assert 'efficiency_ratio' in df_loaded.columns
    assert 'volume_ratio' in df_loaded.columns


def test_pipeline_with_minimal_data():
    """Test pipeline handles minimal data gracefully."""
    # Very few data points
    df = pd.DataFrame({
        'high': [42000, 42100, 42200],
        'low': [41800, 41900, 42000],
        'close': [41900, 42000, 42100],
        'volume': [100, 110, 105]
    })
    
    df_features = calculate_all_features(df)
    
    # Should complete without errors
    # Many features will be NaN due to insufficient data, which is expected
    assert len(df_features) == 3


def test_pipeline_preserves_original_columns():
    """Test that pipeline preserves original OHLCV columns."""
    df = pd.DataFrame({
        'high': [42000, 42100, 42200] * 20,
        'low': [41800, 41900, 42000] * 20,
        'close': [41900, 42000, 42100] * 20,
        'volume': [100, 110, 105] * 20
    })
    
    original_cols = set(df.columns)
    
    df_features = calculate_all_features(df)
    
    # Original columns should still be present
    for col in original_cols:
        assert col in df_features.columns


def test_feature_calculations_are_deterministic():
    """Test that feature calculations are deterministic (same input = same output)."""
    np.random.seed(42)
    df = pd.DataFrame({
        'high': 42000 + np.random.randn(50) * 500,
        'low': 41000 + np.random.randn(50) * 500,
        'close': 41500 + np.random.randn(50) * 500,
        'volume': 100 + np.abs(np.random.randn(50) * 20)
    })
    
    # Calculate twice
    df1 = calculate_all_features(df.copy())
    df2 = calculate_all_features(df.copy())
    
    # Results should be identical
    assert df1['atr'].equals(df2['atr'])
    assert df1['efficiency_ratio'].equals(df2['efficiency_ratio'])
    assert df1['volume_ratio'].equals(df2['volume_ratio'])


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
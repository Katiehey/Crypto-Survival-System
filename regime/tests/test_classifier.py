"""
Tests for regime classifier.
"""

import pytest
import pandas as pd
import numpy as np
from regime.classifier import (
    Regime,
    RegimeClassification,
    RegimeClassifier,
    get_regime_statistics
)


@pytest.fixture
def classifier():
    """Create classifier instance."""
    return RegimeClassifier()


def test_classifier_initialization(classifier):
    """Test classifier can be initialized."""
    assert classifier is not None
    assert hasattr(classifier, 'classify_regime')


def test_classify_strong_trend(classifier):
    """Test classification of strong trend."""
    result = classifier.classify_regime(
        efficiency_ratio=0.8,
        atr_percentile=50,
        volume_percentile=60,
        volume_regime='normal'
    )
    
    assert result.regime == Regime.TREND
    assert result.confidence > 0.7
    assert result.tradable == True


def test_classify_quiet_range(classifier):
    """Test classification of quiet range."""
    result = classifier.classify_regime(
        efficiency_ratio=0.2,
        atr_percentile=25,
        volume_percentile=40,
        volume_regime='normal'
    )
    
    assert result.regime == Regime.RANGE
    assert result.confidence > 0.4
    assert result.tradable == True


def test_classify_chaos(classifier):
    """Test classification of chaotic market."""
    result = classifier.classify_regime(
        efficiency_ratio=0.15,
        atr_percentile=85,
        volume_percentile=70,
        volume_regime='high'
    )
    
    assert result.regime == Regime.CHAOS
    assert result.tradable == False


def test_classify_very_low_volume(classifier):
    """Test that very low volume triggers NO_TRADE."""
    result = classifier.classify_regime(
        efficiency_ratio=0.7,  # Even with good trend
        atr_percentile=50,
        volume_percentile=10,  # Very low volume
        volume_regime='low'
    )
    
    assert result.regime == Regime.NO_TRADE
    assert result.tradable == False


def test_classify_invalid_data_nan(classifier):
    """Test handling of NaN values."""
    result = classifier.classify_regime(
        efficiency_ratio=np.nan,
        atr_percentile=50,
        volume_percentile=50,
        volume_regime='normal'
    )
    
    assert result.regime == Regime.NO_TRADE
    assert result.confidence == 0.0
    assert result.tradable == False


def test_classify_invalid_data_out_of_range(classifier):
    """Test handling of out-of-range values."""
    result = classifier.classify_regime(
        efficiency_ratio=1.5,  # Invalid (>1)
        atr_percentile=50,
        volume_percentile=50,
        volume_regime='normal'
    )
    
    assert result.regime == Regime.NO_TRADE


def test_classify_ambiguous_conditions(classifier):
    """Test classification of ambiguous conditions."""
    result = classifier.classify_regime(
        efficiency_ratio=0.45,  # Between thresholds
        atr_percentile=50,
        volume_percentile=50,
        volume_regime='normal'
    )
    
    # Should classify but with low confidence
    assert result.confidence < 0.6


def test_trend_with_high_volume(classifier):
    """Test that high volume increases trend confidence."""
    result_normal = classifier.classify_regime(
        efficiency_ratio=0.7,
        atr_percentile=50,
        volume_percentile=50,
        volume_regime='normal'
    )
    
    result_high = classifier.classify_regime(
        efficiency_ratio=0.7,
        atr_percentile=50,
        volume_percentile=80,
        volume_regime='high'
    )
    
    # High volume should give higher confidence
    assert result_high.confidence >= result_normal.confidence


def test_classify_dataframe(classifier):
    """Test classifying entire DataFrame."""
    df = pd.DataFrame({
        'efficiency_ratio': [0.8, 0.2, 0.15, 0.5],
        'atr_percentile': [50, 30, 85, 50],
        'volume_percentile': [60, 40, 70, 50],
        'volume_regime': ['normal', 'normal', 'high', 'normal']
    })
    
    df_classified = classifier.classify_dataframe(df)
    
    # Check columns added
    assert 'regime' in df_classified.columns
    assert 'regime_confidence' in df_classified.columns
    assert 'regime_tradable' in df_classified.columns
    
    # Check classifications
    assert df_classified['regime'].iloc[0] == 'trend'
    assert df_classified['regime'].iloc[1] == 'range'
    assert df_classified['regime'].iloc[2] == 'chaos'


def test_classify_dataframe_missing_columns(classifier):
    """Test error handling for missing columns."""
    df = pd.DataFrame({
        'efficiency_ratio': [0.5, 0.6]
        # Missing other required columns
    })
    
    with pytest.raises(ValueError, match="Missing required columns"):
        classifier.classify_dataframe(df)


def test_get_regime_statistics():
    """Test regime statistics calculation."""
    df = pd.DataFrame({
        'regime': ['trend', 'trend', 'range', 'chaos', 'trend'],
        'regime_confidence': [0.8, 0.75, 0.6, 0.5, 0.85],
        'regime_tradable': [True, True, True, False, True]
    })
    
    stats = get_regime_statistics(df)
    
    assert stats['total_periods'] == 5
    assert stats['regime_counts']['trend'] == 3
    assert stats['regime_counts']['range'] == 1
    assert stats['regime_counts']['chaos'] == 1
    assert stats['tradable_periods'] == 4
    assert 'mean_confidence' in stats


def test_regime_enum_values():
    """Test that regime enum has expected values."""
    assert Regime.TREND.value == "trend"
    assert Regime.RANGE.value == "range"
    assert Regime.CHAOS.value == "chaos"
    assert Regime.NO_TRADE.value == "no_trade"


def test_regime_classification_repr():
    """Test RegimeClassification string representation."""
    classification = RegimeClassification(
        regime=Regime.TREND,
        confidence=0.85,
        tradable=True,
        reasons=["Test reason"]
    )
    
    repr_str = repr(classification)
    assert "trend" in repr_str
    assert "0.85" in repr_str
    assert "True" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
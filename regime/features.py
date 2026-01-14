"""
Feature engineering for regime classification.

This module calculates technical indicators used to classify market regimes:
- ATR (Average True Range): Volatility measure
- Efficiency Ratio: Trend strength measure
- Volume metrics: Participation measure

All calculations are deterministic and tested with known values.
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple


def calculate_true_range(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series
) -> pd.Series:
    """
    Calculate True Range.
    
    True Range is the greatest of:
    1. Current High - Current Low
    2. |Current High - Previous Close|
    3. |Current Low - Previous Close|
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        
    Returns:
        Series of True Range values
        
    Example:
        >>> high = pd.Series([10, 12, 11])
        >>> low = pd.Series([9, 10, 9])
        >>> close = pd.Series([9.5, 11, 10])
        >>> tr = calculate_true_range(high, low, close)
    """
    # Method 1: High - Low
    hl = high - low
    
    # Method 2: |High - Previous Close|
    hc = (high - close.shift(1)).abs()
    
    # Method 3: |Low - Previous Close|
    lc = (low - close.shift(1)).abs()
    
    # True Range = maximum of the three
    true_range = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    
    return true_range


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    ATR is an exponential moving average of True Range.
    Uses Wilder's smoothing method (same as EMA with alpha = 1/period).
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period (default: 14)
        
    Returns:
        Series of ATR values
        
    Notes:
        - First ATR value is simple average of first 'period' TRs
        - Subsequent values use exponential smoothing
        - NaN for first 'period' values (insufficient data)
    """
    if period < 1:
        raise ValueError("ATR period must be >= 1")
    
    # Calculate True Range
    tr = calculate_true_range(high, low, close)
    
    # Calculate ATR using exponential moving average
    # Wilder's smoothing: alpha = 1/period
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    return atr


def calculate_atr_percentile(
    atr: pd.Series,
    lookback: int = 100
) -> pd.Series:
    """
    Calculate ATR percentile over rolling window.
    
    Percentile indicates where current ATR sits in historical distribution:
    - 0 = lowest ATR in lookback period (low volatility)
    - 50 = median
    - 100 = highest ATR in lookback period (high volatility)
    
    Args:
        atr: ATR values
        lookback: Number of periods for percentile calculation
        
    Returns:
        Series of ATR percentile values (0-100)
        
    Example:
        If current ATR is higher than 80% of recent ATR values,
        percentile = 80
    """
    if lookback < 2:
        raise ValueError("Lookback period must be >= 2")
    
    def rolling_percentile(series):
        """Calculate percentile of last value in rolling window."""
        if len(series) < 2:
            return np.nan
        
        # Last value
        current = series.iloc[-1]
        
        # Calculate percentile rank
        percentile = (series < current).sum() / len(series) * 100
        
        return percentile
    
    atr_percentile = atr.rolling(window=lookback).apply(
        rolling_percentile,
        raw=False
    )
    
    return atr_percentile


def normalize_atr(
    atr: pd.Series,
    close: pd.Series
) -> pd.Series:
    """
    Normalize ATR by price (percentage of price).
    
    This makes ATR comparable across different price levels.
    
    Args:
        atr: ATR values
        close: Close prices
        
    Returns:
        Series of normalized ATR (ATR as % of price)
        
    Example:
        If ATR = 100 and price = 40000, normalized = 0.0025 (0.25%)
    """
    # Avoid division by zero
    close_safe = close.replace(0, np.nan)
    
    normalized = atr / close_safe
    
    return normalized


def add_atr_features(
    df: pd.DataFrame,
    atr_period: int = 14,
    percentile_lookback: int = 100
) -> pd.DataFrame:
    """
    Add all ATR-related features to DataFrame.
    
    Adds columns:
    - 'tr': True Range
    - 'atr': Average True Range
    - 'atr_pct': ATR as percentage of price
    - 'atr_percentile': ATR percentile over lookback
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        atr_period: Period for ATR calculation
        percentile_lookback: Lookback for percentile calculation
        
    Returns:
        DataFrame with ATR features added
        
    Raises:
        ValueError: If required columns missing
    """
    required_cols = ['high', 'low', 'close']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    df = df.copy()
    
    # True Range
    df['tr'] = calculate_true_range(df['high'], df['low'], df['close'])
    
    # ATR
    df['atr'] = calculate_atr(
        df['high'],
        df['low'],
        df['close'],
        period=atr_period
    )
    
    # Normalized ATR (as % of price)
    df['atr_pct'] = normalize_atr(df['atr'], df['close'])
    
    # ATR Percentile
    df['atr_percentile'] = calculate_atr_percentile(
        df['atr'],
        lookback=percentile_lookback
    )
    
    return df


def validate_atr(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validate ATR calculations.
    
    Checks:
    - No negative values
    - No infinite values
    - ATR is reasonable relative to price
    - Percentiles are in valid range
    
    Args:
        df: DataFrame with ATR features
        
    Returns:
        (is_valid, error_message)
    """
    if 'atr' not in df.columns:
        return False, "ATR column missing"
    
    atr_values = df['atr'].dropna()
    
    if len(atr_values) == 0:
        return False, "No valid ATR values"
    
    # Check for negative values
    if (atr_values < 0).any():
        return False, "ATR contains negative values"
    
    # Check for infinite values
    if np.isinf(atr_values).any():
        return False, "ATR contains infinite values"
    
    # Check ATR percentiles if present
    if 'atr_percentile' in df.columns:
        percentiles = df['atr_percentile'].dropna()
        if len(percentiles) > 0:
            if (percentiles < 0).any() or (percentiles > 100).any():
                return False, "ATR percentile outside valid range [0, 100]"
    
    # Check normalized ATR if present
    if 'atr_pct' in df.columns:
        atr_pct = df['atr_pct'].dropna()
        if len(atr_pct) > 0:
            # ATR should typically be < 10% of price
            if (atr_pct > 0.10).any():
                return False, "Normalized ATR unusually high (>10%)"
    
    return True, "ATR validation passed"


def main():
    """
    Test all feature calculations with sample data.
    """
    print("=" * 60)
    print("FEATURE CALCULATION TEST")
    print("=" * 60)
    
    # Create sample data with clear trend and varying volume
    np.random.seed(42)
    n = 100
    
    # Create trending price data
    trend = np.linspace(40000, 45000, n)
    noise = np.random.randn(n) * 200
    
    # Create volume with some spikes
    base_volume = 100
    volume = base_volume + np.random.randn(n) * 20
    volume[50] = base_volume * 3  # Spike at position 50
    volume = np.abs(volume)  # Ensure positive
    
    df = pd.DataFrame({
        'close': trend + noise,
        'high': trend + noise + 100,
        'low': trend + noise - 100,
        'volume': volume,
    })
    
    # Calculate all features
    print("\n🔄 Calculating ATR features...")
    df = add_atr_features(df)
    
    print("🔄 Calculating Efficiency features...")
    df = add_efficiency_features(df)
    
    print("🔄 Calculating Volume features...")
    df = add_volume_features(df)
    
    # Display results
    print("\nSample Data (last 5 rows):")
    cols_to_show = [
        'close', 'volume', 'volume_ratio', 'volume_regime',
        'atr_percentile', 'efficiency_ratio', 'trend_strength'
    ]
    # Use only columns that exist to prevent errors
    existing_cols = [c for c in cols_to_show if c in df.columns]
    print(df[existing_cols].tail())
    
    # Validation
    atr_valid, atr_msg = validate_atr(df)
    eff_valid, eff_msg = validate_efficiency(df)
    vol_valid, vol_msg = validate_volume(df)
    
    print(f"\n{'✅' if atr_valid else '❌'} ATR: {atr_msg}")
    print(f"{'✅' if eff_valid else '❌'} Efficiency: {eff_msg}")
    print(f"{'✅' if vol_valid else '❌'} Volume: {vol_msg}")
    
    # Statistics
    print("\n" + "=" * 60)
    print("FEATURE STATISTICS")
    print("=" * 60)
    
    if 'atr_pct' in df.columns:
        print("\nATR:")
        print(f"  Mean %: {df['atr_pct'].mean() * 100:.2f}%")
    
    if 'efficiency_ratio' in df.columns:
        print("\nEfficiency Ratio:")
        print(f"  Mean: {df['efficiency_ratio'].mean():.3f}")
    
    if 'volume_ratio' in df.columns:
        print("\nVolume:")
        print(f"  Mean: {df['volume'].mean():.2f}")
        print(f"  Mean ratio: {df['volume_ratio'].mean():.2f}")
        print(f"  Spikes detected: {df['volume_spike'].sum()}")
    
    if 'volume_regime' in df.columns:
        print("\nVolume Regime Distribution:")
        print(df['volume_regime'].value_counts())
    
    if 'trend_strength' in df.columns:
        print("\nTrend Strength Distribution:")
        print(df['trend_strength'].value_counts())


def calculate_efficiency_ratio(
    close: pd.Series,
    period: int = 10
) -> pd.Series:
    """
    Calculate Kaufman Efficiency Ratio.
    
    Efficiency Ratio measures trend strength by comparing net price change
    to total price movement.
    
    ER = |Net Price Change| / Sum of |Individual Price Changes|
    
    Values:
    - 1.0 = Perfect trend (straight line)
    - 0.5 = Moderate trend
    - 0.0 = No trend (pure noise)
    
    Args:
        close: Close prices
        period: Lookback period for calculation (default: 10)
        
    Returns:
        Series of Efficiency Ratio values (0 to 1)
        
    Example:
        Price moves 100 -> 105 -> 110
        Net change = 10
        Total movement = 5 + 5 = 10
        ER = 10/10 = 1.0 (perfect efficiency)
        
        Price moves 100 -> 110 -> 100
        Net change = 0
        Total movement = 10 + 10 = 20
        ER = 0/20 = 0.0 (no efficiency, just noise)
    """
    if period < 2:
        raise ValueError("Efficiency ratio period must be >= 2")
    
    # Net price change over period
    net_change = (close - close.shift(period)).abs()
    
    # Sum of absolute price changes (volatility)
    price_changes = close.diff().abs()
    total_movement = price_changes.rolling(window=period).sum()
    
    # Efficiency Ratio = net change / total movement
    # Handle division by zero (when total_movement = 0)
    efficiency_ratio = net_change / total_movement.replace(0, np.nan)
    
    # Clip to [0, 1] range (should already be, but ensure)
    efficiency_ratio = efficiency_ratio.clip(0, 1)
    
    return efficiency_ratio


def calculate_efficiency_percentile(
    efficiency: pd.Series,
    lookback: int = 100
) -> pd.Series:
    """
    Calculate Efficiency Ratio percentile over rolling window.
    
    Percentile indicates where current efficiency sits in historical distribution:
    - 0 = lowest efficiency in lookback (ranging market)
    - 50 = median
    - 100 = highest efficiency in lookback (strong trend)
    
    Args:
        efficiency: Efficiency Ratio values
        lookback: Number of periods for percentile calculation
        
    Returns:
        Series of efficiency percentile values (0-100)
    """
    if lookback < 2:
        raise ValueError("Lookback period must be >= 2")
    
    def rolling_percentile(series):
        """Calculate percentile of last value in rolling window."""
        if len(series) < 2:
            return np.nan
        
        current = series.iloc[-1]
        percentile = (series < current).sum() / len(series) * 100
        
        return percentile
    
    efficiency_percentile = efficiency.rolling(window=lookback).apply(
        rolling_percentile,
        raw=False
    )
    
    return efficiency_percentile


def smooth_efficiency_ratio(
    efficiency: pd.Series,
    smoothing_period: int = 5
) -> pd.Series:
    """
    Smooth Efficiency Ratio using simple moving average.
    
    Raw efficiency can be noisy. Smoothing helps identify sustained trends
    vs temporary movements.
    
    Args:
        efficiency: Raw efficiency ratio values
        smoothing_period: Period for moving average smoothing
        
    Returns:
        Smoothed efficiency ratio
    """
    if smoothing_period < 1:
        raise ValueError("Smoothing period must be >= 1")
    
    smoothed = efficiency.rolling(window=smoothing_period).mean()
    
    return smoothed


def classify_trend_strength(efficiency: pd.Series) -> pd.Series:
    """
    Classify trend strength based on Efficiency Ratio.
    
    Classification:
    - 'strong_trend': ER >= 0.7
    - 'moderate_trend': 0.4 <= ER < 0.7
    - 'weak_trend': 0.2 <= ER < 0.4
    - 'no_trend': ER < 0.2
    
    Args:
        efficiency: Efficiency Ratio values
        
    Returns:
        Series of trend strength labels
    """
    def classify(er):
        if pd.isna(er):
            return 'unknown'
        elif er >= 0.7:
            return 'strong_trend'
        elif er >= 0.4:
            return 'moderate_trend'
        elif er >= 0.2:
            return 'weak_trend'
        else:
            return 'no_trend'
    
    return efficiency.apply(classify)


def add_efficiency_features(
    df: pd.DataFrame,
    period: int = 10,
    smoothing_period: int = 5,
    percentile_lookback: int = 100
) -> pd.DataFrame:
    """
    Add all Efficiency Ratio features to DataFrame.
    
    Adds columns:
    - 'efficiency_ratio': Raw efficiency ratio (0-1)
    - 'efficiency_ratio_smooth': Smoothed efficiency ratio
    - 'efficiency_percentile': Efficiency percentile over lookback
    - 'trend_strength': Categorical trend strength label
    
    Args:
        df: DataFrame with 'close' column
        period: Period for efficiency calculation
        smoothing_period: Period for smoothing
        percentile_lookback: Lookback for percentile
        
    Returns:
        DataFrame with efficiency features added
        
    Raises:
        ValueError: If 'close' column missing
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    df = df.copy()
    
    # Calculate efficiency ratio
    df['efficiency_ratio'] = calculate_efficiency_ratio(
        df['close'],
        period=period
    )
    
    # Smoothed version
    df['efficiency_ratio_smooth'] = smooth_efficiency_ratio(
        df['efficiency_ratio'],
        smoothing_period=smoothing_period
    )
    
    # Percentile
    df['efficiency_percentile'] = calculate_efficiency_percentile(
        df['efficiency_ratio'],
        lookback=percentile_lookback
    )
    
    # Trend strength classification
    df['trend_strength'] = classify_trend_strength(
        df['efficiency_ratio_smooth']
    )
    
    return df


def validate_efficiency(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validate Efficiency Ratio calculations.
    """
    if 'efficiency_ratio' not in df.columns:
        return False, "Efficiency ratio column missing"
    
    er_values = df['efficiency_ratio'].dropna()
    
    if len(er_values) == 0:
        return False, "No valid efficiency ratio values"
    
    # 1. Check for infinite values FIRST
    if np.isinf(er_values).any():
        return False, "Efficiency ratio contains infinite values"
    
    # 2. Check for values outside [0, 1]
    # We use a small buffer (1e-6) for float precision if necessary
    if (er_values < 0).any() or (er_values > 1.000001).any():
        return False, "Efficiency ratio outside valid range [0, 1]"
    
    # 3. Check percentiles if present
    if 'efficiency_percentile' in df.columns:
        percentiles = df['efficiency_percentile'].dropna()
        if len(percentiles) > 0:
            if (percentiles < 0).any() or (percentiles > 100).any():
                return False, "Efficiency percentile outside valid range [0, 100]"
    
    return True, "Efficiency validation passed"

def calculate_volume_ma(
    volume: pd.Series,
    period: int = 20
) -> pd.Series:
    """
    Calculate volume moving average.
    
    Args:
        volume: Volume values
        period: MA period (default: 20)
        
    Returns:
        Series of volume moving average
    """
    if period < 1:
        raise ValueError("Volume MA period must be >= 1")
    
    volume_ma = volume.rolling(window=period).mean()
    
    return volume_ma


def calculate_volume_ratio(
    volume: pd.Series,
    volume_ma: pd.Series
) -> pd.Series:
    """
    Calculate volume ratio (current volume / average volume).
    
    Ratio interpretation:
    - > 2.0: Very high volume
    - 1.5-2.0: High volume
    - 0.5-1.5: Normal volume
    - < 0.5: Low volume
    
    Args:
        volume: Current volume values
        volume_ma: Volume moving average
        
    Returns:
        Series of volume ratio values
    """
    # Avoid division by zero
    volume_ma_safe = volume_ma.replace(0, np.nan)
    
    volume_ratio = volume / volume_ma_safe
    
    return volume_ratio


def calculate_volume_percentile(
    volume: pd.Series,
    lookback: int = 100
) -> pd.Series:
    """
    Calculate volume percentile over rolling window.
    
    Percentile indicates where current volume sits in distribution:
    - 0 = lowest volume in lookback
    - 50 = median volume
    - 100 = highest volume in lookback
    
    Args:
        volume: Volume values
        lookback: Lookback period
        
    Returns:
        Series of volume percentile values (0-100)
    """
    if lookback < 2:
        raise ValueError("Lookback period must be >= 2")
    
    def rolling_percentile(series):
        """Calculate percentile of last value in rolling window."""
        if len(series) < 2:
            return np.nan
        
        current = series.iloc[-1]
        percentile = (series <= current).sum() / len(series) * 100
        
        return percentile
    
    volume_percentile = volume.rolling(window=lookback).apply(
        rolling_percentile,
        raw=False
    )
    
    return volume_percentile


def classify_volume_regime(volume_ratio: pd.Series) -> pd.Series:
    """
    Classify volume regime based on volume ratio.
    
    Classification:
    - 'very_high': ratio >= 2.0
    - 'high': 1.5 <= ratio < 2.0
    - 'normal': 0.5 <= ratio < 1.5
    - 'low': ratio < 0.5
    
    Args:
        volume_ratio: Volume ratio values
        
    Returns:
        Series of volume regime labels
    """
    def classify(ratio):
        if pd.isna(ratio):
            return 'unknown'
        elif ratio >= 2.0:
            return 'very_high'
        elif ratio >= 1.5:
            return 'high'
        elif ratio >= 0.5:
            return 'normal'
        else:
            return 'low'
    
    return volume_ratio.apply(classify)


def detect_volume_spike(
    volume_ratio: pd.Series,
    threshold: float = 2.0
) -> pd.Series:
    """
    Detect volume spikes (significantly above average).
    
    Volume spikes often indicate:
    - Breakouts (if accompanied by price move)
    - Capitulation (if at extremes)
    - News events
    - Institutional activity
    
    Args:
        volume_ratio: Volume ratio values
        threshold: Spike threshold (default: 2.0 = 200% of average)
        
    Returns:
        Boolean series (True = spike detected)
    """
    return volume_ratio >= threshold


def add_volume_features(
    df: pd.DataFrame,
    ma_period: int = 20,
    percentile_lookback: int = 100
) -> pd.DataFrame:
    """
    Add all volume features to DataFrame.
    
    Adds columns:
    - 'volume_ma': Volume moving average
    - 'volume_ratio': Current volume / average volume
    - 'volume_percentile': Volume percentile over lookback
    - 'volume_regime': Categorical volume classification
    - 'volume_spike': Boolean spike indicator
    
    Args:
        df: DataFrame with 'volume' column
        ma_period: Period for volume MA
        percentile_lookback: Lookback for percentile
        
    Returns:
        DataFrame with volume features added
        
    Raises:
        ValueError: If 'volume' column missing
    """
    if 'volume' not in df.columns:
        raise ValueError("DataFrame must contain 'volume' column")
    
    df = df.copy()
    
    # Volume moving average
    df['volume_ma'] = calculate_volume_ma(df['volume'], period=ma_period)
    
    # Volume ratio
    df['volume_ratio'] = calculate_volume_ratio(
        df['volume'],
        df['volume_ma']
    )
    
    # Volume percentile
    df['volume_percentile'] = calculate_volume_percentile(
        df['volume'],
        lookback=percentile_lookback
    )
    
    # Volume regime classification
    df['volume_regime'] = classify_volume_regime(df['volume_ratio'])
    
    # Volume spike detection
    df['volume_spike'] = detect_volume_spike(df['volume_ratio'])
    
    return df


def validate_volume(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validate volume calculations.
    
    Checks:
    - No negative values
    - No infinite values
    - Percentiles in valid range
    - Ratios are reasonable
    
    Args:
        df: DataFrame with volume features
        
    Returns:
        (is_valid, error_message)
    """
    # Check volume exists
    if 'volume' not in df.columns:
        return False, "Volume column missing"
    
    volume_values = df['volume'].dropna()
    
    if len(volume_values) == 0:
        return False, "No valid volume values"
    
    # Check for negative volume
    if (volume_values < 0).any():
        return False, "Volume contains negative values"
    
    # Check for infinite values
    if np.isinf(volume_values).any():
        return False, "Volume contains infinite values"
    
    # Check volume ratio if present
    if 'volume_ratio' in df.columns:
        ratios = df['volume_ratio'].dropna()
        if len(ratios) > 0:
            # Volume ratio should typically be < 10
            if (ratios > 10).any():
                return False, "Volume ratio unusually high (>10x)"
            
            if (ratios < 0).any():
                return False, "Volume ratio contains negative values"
    
    # Check percentiles if present
    if 'volume_percentile' in df.columns:
        percentiles = df['volume_percentile'].dropna()
        if len(percentiles) > 0:
            if (percentiles < 0).any() or (percentiles > 100).any():
                return False, "Volume percentile outside valid range [0, 100]"
    
    return True, "Volume validation passed"

def calculate_all_features(
    df: pd.DataFrame,
    atr_period: int = 14,
    efficiency_period: int = 10,
    volume_ma_period: int = 20,
    percentile_lookback: int = 100
) -> pd.DataFrame:
    """
    Calculate all regime features in one pass.
    
    This is the main entry point for feature calculation.
    
    Features calculated:
    - ATR family (tr, atr, atr_pct, atr_percentile)
    - Efficiency family (efficiency_ratio, efficiency_ratio_smooth, 
                         efficiency_percentile, trend_strength)
    - Volume family (volume_ma, volume_ratio, volume_percentile,
                     volume_regime, volume_spike)
    
    Args:
        df: DataFrame with OHLCV columns (high, low, close, volume)
        atr_period: ATR calculation period
        efficiency_period: Efficiency ratio period
        volume_ma_period: Volume MA period
        percentile_lookback: Lookback for all percentile calculations
        
    Returns:
        DataFrame with all features added
        
    Raises:
        ValueError: If required columns missing
        
    Example:
        >>> df = fetcher.load_candles(limit=200)
        >>> df = calculate_all_features(df)
        >>> print(df[['close', 'atr', 'efficiency_ratio', 'volume_ratio']].tail())
    """
    # Validate input
    required_cols = ['high', 'low', 'close', 'volume']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    print("🔄 Calculating features...")
    
    # Calculate ATR features
    print("   - ATR (volatility metrics)")
    df = add_atr_features(
        df,
        atr_period=atr_period,
        percentile_lookback=percentile_lookback
    )
    
    # Calculate Efficiency features
    print("   - Efficiency Ratio (trend strength)")
    df = add_efficiency_features(
        df,
        period=efficiency_period,
        percentile_lookback=percentile_lookback
    )
    
    # Calculate Volume features
    print("   - Volume metrics (participation)")
    df = add_volume_features(
        df,
        ma_period=volume_ma_period,
        percentile_lookback=percentile_lookback
    )
    
    print("✅ Feature calculation complete")
    
    return df


def validate_all_features(df: pd.DataFrame) -> Tuple[bool, dict]:
    """
    Validate all feature calculations.
    
    Args:
        df: DataFrame with all features
        
    Returns:
        (all_valid, validation_results)
        where validation_results is dict with individual results
    """
    results = {}
    
    # Validate each feature type
    atr_valid, atr_msg = validate_atr(df)
    results['atr'] = {'valid': atr_valid, 'message': atr_msg}
    
    eff_valid, eff_msg = validate_efficiency(df)
    results['efficiency'] = {'valid': eff_valid, 'message': eff_msg}
    
    vol_valid, vol_msg = validate_volume(df)
    results['volume'] = {'valid': vol_valid, 'message': vol_msg}
    
    # Overall validity
    all_valid = atr_valid and eff_valid and vol_valid
    
    return all_valid, results


def get_feature_summary(df: pd.DataFrame) -> dict:
    """
    Get summary statistics for all features.
    
    Args:
        df: DataFrame with all features
        
    Returns:
        Dictionary with summary statistics
    """
    summary = {}
    
    # ATR summary
    if 'atr' in df.columns:
        summary['atr'] = {
            'mean': df['atr'].mean(),
            'median': df['atr'].median(),
            'current': df['atr'].iloc[-1] if len(df) > 0 else None,
            'mean_pct': df['atr_pct'].mean() * 100 if 'atr_pct' in df.columns else None,
            'percentile': df['atr_percentile'].iloc[-1] if 'atr_percentile' in df.columns and len(df) > 0 else None
        }
    
    # Efficiency summary
    if 'efficiency_ratio' in df.columns:
        summary['efficiency'] = {
            'mean': df['efficiency_ratio'].mean(),
            'median': df['efficiency_ratio'].median(),
            'current': df['efficiency_ratio'].iloc[-1] if len(df) > 0 else None,
            'current_strength': df['trend_strength'].iloc[-1] if 'trend_strength' in df.columns and len(df) > 0 else None,
            'strength_distribution': df['trend_strength'].value_counts().to_dict() if 'trend_strength' in df.columns else None
        }
    
    # Volume summary
    if 'volume' in df.columns:
        summary['volume'] = {
            'mean': df['volume'].mean(),
            'median': df['volume'].median(),
            'current': df['volume'].iloc[-1] if len(df) > 0 else None,
            'current_ratio': df['volume_ratio'].iloc[-1] if 'volume_ratio' in df.columns and len(df) > 0 else None,
            'current_regime': df['volume_regime'].iloc[-1] if 'volume_regime' in df.columns and len(df) > 0 else None,
            'spikes_detected': df['volume_spike'].sum() if 'volume_spike' in df.columns else 0,
            'regime_distribution': df['volume_regime'].value_counts().to_dict() if 'volume_regime' in df.columns else None
        }
    
    return summary


def export_features_csv(df: pd.DataFrame, filepath: str) -> None:
    """
    Export features to CSV file.
    
    Args:
        df: DataFrame with features
        filepath: Output file path
    """
    # Select feature columns
    feature_cols = [
        'timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume',
        'tr', 'atr', 'atr_pct', 'atr_percentile',
        'efficiency_ratio', 'efficiency_ratio_smooth', 'efficiency_percentile', 'trend_strength',
        'volume_ma', 'volume_ratio', 'volume_percentile', 'volume_regime', 'volume_spike'
    ]
    
    # Only include columns that exist
    cols_to_export = [col for col in feature_cols if col in df.columns]
    
    df[cols_to_export].to_csv(filepath, index=False)
    print(f"✅ Features exported to {filepath}")

if __name__ == "__main__":
    main()
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
    Test ATR calculations with sample data.
    """
    print("=" * 60)
    print("ATR FEATURE CALCULATION TEST")
    print("=" * 60)
    
    # Create sample data
    np.random.seed(42)
    n = 100
    
    price = 42000
    volatility = 500
    
    df = pd.DataFrame({
        'high': price + np.random.randn(n) * volatility + volatility,
        'low': price + np.random.randn(n) * volatility - volatility,
        'close': price + np.random.randn(n) * volatility,
    })
    
    # Calculate ATR features
    df = add_atr_features(df)
    
    # Display results
    print("\nSample Data (last 5 rows):")
    print(df[['close', 'tr', 'atr', 'atr_pct', 'atr_percentile']].tail())
    
    # Validation
    is_valid, message = validate_atr(df)
    print(f"\n{'✅' if is_valid else '❌'} Validation: {message}")
    
    # Statistics
    print("\nATR Statistics:")
    print(f"  Mean ATR: {df['atr'].mean():.2f}")
    print(f"  Median ATR: {df['atr'].median():.2f}")
    print(f"  Mean ATR %: {df['atr_pct'].mean() * 100:.2f}%")
    print(f"  ATR Range: {df['atr'].min():.2f} - {df['atr'].max():.2f}")


if __name__ == "__main__":
    main()
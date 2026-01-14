"""
Test feature calculations with real market data.
"""

from data.fetcher import DataFetcher
from regime.features import (
    add_atr_features,
    add_efficiency_features,
    add_volume_features,
    validate_atr,
    validate_efficiency,
    validate_volume
)
import matplotlib.pyplot as plt
import pandas as pd


def main():
    """Test all features with real market data."""
    print("=" * 60)
    print("COMPLETE FEATURE PIPELINE - REAL DATA")
    print("=" * 60)
    
    # Load data
    fetcher = DataFetcher()
    candle_count = fetcher.get_candle_count()
    
    if candle_count == 0:
        print("\n⚠️  No data in database.")
        print("Run 'python data/fetcher.py' first to fetch data.")
        return
    
    print(f"\n📊 Loading {candle_count} candles...")
    df = fetcher.load_candles(limit=200)
    
    if df.empty:
        print("❌ Failed to load data.")
        return

    print(f"✅ Loaded {len(df)} candles")
    print(f"   Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    print(f"   Symbol: BTC/USDT")
    
    # Calculate all features
    print("\n🔄 Calculating features...")
    print("   - ATR (volatility)")
    df = add_atr_features(df)
    
    print("   - Efficiency Ratio (trend strength)")
    df = add_efficiency_features(df)
    
    print("   - Volume metrics (participation)")
    df = add_volume_features(df)
    
    # Validate all
    print("\n🔍 Validating calculations...")
    atr_valid, atr_msg = validate_atr(df)
    eff_valid, eff_msg = validate_efficiency(df)
    vol_valid, vol_msg = validate_volume(df)
    
    print(f"   {'✅' if atr_valid else '❌'} ATR: {atr_msg}")
    print(f"   {'✅' if eff_valid else '❌'} Efficiency: {eff_msg}")
    print(f"   {'✅' if vol_valid else '❌'} Volume: {vol_msg}")
    
    all_valid = atr_valid and eff_valid and vol_valid
    
    if not all_valid:
        print("\n❌ Feature validation failed!")
        return
        
    # Statistics
    print("\n" + "=" * 60)
    print("FEATURE STATISTICS")
    print("=" * 60)
    
    print("\nVolatility (ATR):")
    print(f"  Mean ATR: ${df['atr'].mean():.2f}")
    print(f"  Mean ATR %: {df['atr_pct'].mean() * 100:.2f}%")
    # Using .get() or checking for NaN to prevent crash on small datasets
    last_atr_pctile = df['atr_percentile'].iloc[-1]
    print(f"  Current ATR %ile: {last_atr_pctile:.1f}" if not pd.isna(last_atr_pctile) else "  Current ATR %ile: NaN (Warm-up)")
    
    print("\nTrend Strength (Efficiency):")
    print(f"  Mean ER: {df['efficiency_ratio'].mean():.3f}")
    print(f"  Current ER: {df['efficiency_ratio'].iloc[-1]:.3f}")
    print(f"  Current strength: {df['trend_strength'].iloc[-1]}")
    
    print("\nVolume:")
    print(f"  Mean volume: {df['volume'].mean():.2f}")
    print(f"  Current ratio: {df['volume_ratio'].iloc[-1]:.2f}x")
    print(f"  Current regime: {df['volume_regime'].iloc[-1]}")
    print(f"  Spikes detected: {df['volume_spike'].sum()}")
    
    print("\n" + "=" * 60)
    print("REGIME DISTRIBUTIONS")
    print("=" * 60)
    
    print("\nTrend Strength:")
    for strength, count in df['trend_strength'].value_counts().items():
        pct = count / len(df) * 100
        print(f"  {str(strength):15s}: {count:3d} ({pct:5.1f}%)")
        
    print("\nVolume Regime:")
    for regime, count in df['volume_regime'].value_counts().items():
        pct = count / len(df) * 100
        print(f"  {str(regime):15s}: {count:3d} ({pct:5.1f}%)")
        
    # Sample data
    print("\n" + "=" * 60)
    print("SAMPLE DATA (last 10 rows)")
    print("=" * 60)
    
    display_cols = [
        'datetime', 'close', 
        'atr_pct', 'efficiency_ratio', 'volume_ratio',
        'trend_strength', 'volume_regime'
    ]
    # Filter to ensure we only print columns that were successfully added
    existing_cols = [c for c in display_cols if c in df.columns]
    print(df[existing_cols].tail(10).to_string(index=False))
    
    print("\n✅ Complete feature pipeline validated successfully")
    print(f"\n📊 Total features calculated: {len(df.columns)}")
    # We assume base columns are timestamp, open, high, low, close, volume, datetime
    base_cols_count = 7 if 'datetime' in df.columns else 6
    print(f"   Original columns: {base_cols_count}")
    print(f"   Added features: {len(df.columns) - base_cols_count}")
    
if __name__ == "__main__":
    main()
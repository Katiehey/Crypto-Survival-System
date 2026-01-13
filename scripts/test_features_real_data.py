"""
Test feature calculations with real market data.
"""

from data.fetcher import DataFetcher
from regime.features import (
    add_atr_features,
    add_efficiency_features,
    validate_atr,
    validate_efficiency
)
import matplotlib.pyplot as plt


def main():
    """Test all features with real market data."""
    print("=" * 60)
    print("FEATURE CALCULATION - REAL DATA VALIDATION")
    print("=" * 60)
    
    # Load data
    fetcher = DataFetcher()
    candle_count = fetcher.get_candle_count()
    
    if candle_count == 0:
        print("\n⚠️  No data in database.")
        print("Run 'python data/fetcher.py' first to fetch data.")
        return
    
    print(f"\n📊 Loading up to 200 candles from {candle_count} available...")
    df = fetcher.load_candles(limit=200)
    
    if df.empty:
        print("❌ Failed to load data.")
        return

    print(f"✅ Loaded {len(df)} candles")
    print(f"   Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Calculate features
    print("\n🔄 Calculating features...")
    df = add_atr_features(df)
    df = add_efficiency_features(df)
    
    # Validate
    atr_valid, atr_msg = validate_atr(df)
    eff_valid, eff_msg = validate_efficiency(df)
    
    print(f"\n{'✅' if atr_valid else '❌'} ATR: {atr_msg}")
    print(f"{'✅' if eff_valid else '❌'} Efficiency: {eff_msg}")
    
    # Statistics
    print("\n" + "=" * 60)
    print("FEATURE STATISTICS")
    print("=" * 60)
    
    print("\nATR:")
    atr_stats = df['atr'].describe()
    print(f"  Mean: {atr_stats['mean']:.2f}")
    print(f"  Median: {atr_stats['50%']:.2f}")
    print(f"  Mean %: {df['atr_pct'].mean() * 100:.2f}%")
    
    print("\nEfficiency Ratio:")
    er_stats = df['efficiency_ratio'].describe()
    print(f"  Mean: {er_stats['mean']:.3f}")
    print(f"  Median: {er_stats['50%']:.3f}")
    print(f"  Min: {er_stats['min']:.3f}")
    print(f"  Max: {er_stats['max']:.3f}")
    
    print("\nTrend Strength Distribution:")
    strength_counts = df['trend_strength'].value_counts()
    for strength, count in strength_counts.items():
        pct = count / len(df) * 100
        print(f"  {strength.ljust(15)}: {count} ({pct:.1f}%)")
        
    # Sample data
    print("\n" + "=" * 60)
    print("SAMPLE DATA (last 10 rows)")
    print("=" * 60)
    
    # Selecting available columns to avoid KeyError
    display_cols = ['datetime', 'close', 'atr_pct', 'efficiency_ratio', 'trend_strength']
    existing_cols = [c for c in display_cols if c in df.columns]
    
    print(df[existing_cols].tail(10).to_string(index=False))
    
    print("\n✅ Feature calculation complete")

if __name__ == "__main__":
    main()
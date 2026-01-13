"""
Test ATR calculation with real market data.

This script fetches real data and validates ATR calculations.
"""

from data.fetcher import DataFetcher
from regime.features import add_atr_features, validate_atr
import matplotlib.pyplot as plt


def main():
    """Test ATR with real market data."""
    print("=" * 60)
    print("ATR REAL DATA VALIDATION")
    print("=" * 60)
    
    # Load data from database
    fetcher = DataFetcher()
    
    candle_count = fetcher.get_candle_count()
    
    if candle_count == 0:
        print("\n⚠️  No data in database.")
        print("Run 'python data/fetcher.py' first to fetch data.")
        return
    
    print(f"\n📊 Loading {candle_count} candles...")
    
    df = fetcher.load_candles(limit=200)
    
    print(f"✅ Loaded {len(df)} candles")
    print(f"   Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Calculate ATR features
    print("\n🔄 Calculating ATR features...")
    df = add_atr_features(df)
    
    # Validate
    is_valid, message = validate_atr(df)
    print(f"\n{'✅' if is_valid else '❌'} Validation: {message}")
    
    # Display statistics
    print("\n" + "=" * 60)
    print("ATR STATISTICS")
    print("=" * 60)
    
    atr_stats = df['atr'].describe()
    print("\nATR (absolute):")
    print(f"  Mean: {atr_stats['mean']:.2f}")
    print(f"  Median: {atr_stats['50%']:.2f}")
    print(f"  Min: {atr_stats['min']:.2f}")
    print(f"  Max: {atr_stats['max']:.2f}")
    
    atr_pct_stats = df['atr_pct'].describe()
    print("\nATR (% of price):")
    print(f"  Mean: {atr_pct_stats['mean'] * 100:.2f}%")
    print(f"  Median: {atr_pct_stats['50%'] * 100:.2f}%")
    print(f"  Min: {atr_pct_stats['min'] * 100:.2f}%")
    print(f"  Max: {atr_pct_stats['max'] * 100:.2f}%")
    
    # Display sample
    print("\n" + "=" * 60)
    print("SAMPLE DATA (last 10 rows)")
    print("=" * 60)
    print(df[['datetime', 'close', 'atr', 'atr_pct', 'atr_percentile']].tail(10).to_string())
    
    print("\n✅ ATR calculation complete")


if __name__ == "__main__":
    main()
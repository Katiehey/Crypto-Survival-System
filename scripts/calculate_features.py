"""
Calculate and store regime features.

This script:
1. Loads candle data from database
2. Calculates all regime features
3. Validates calculations
4. Exports to CSV for analysis
"""

import os
from datetime import datetime
from data.fetcher import DataFetcher
from regime.features import (
    calculate_all_features,
    validate_all_features,
    get_feature_summary,
    export_features_csv
)
from config.system_config import SYSTEM_CONFIG


def main():
    """Calculate features for stored candle data."""
    print("=" * 60)
    print("FEATURE CALCULATION PIPELINE")
    print("=" * 60)
    
    # Load data
    fetcher = DataFetcher()
    candle_count = fetcher.get_candle_count()
    
    if candle_count == 0:
        print("\n❌ No data in database.")
        print("Run 'python data/fetcher.py' first to fetch data.")
        return 1
    
    print(f"\n📊 Loading candles from database...")
    print(f"   Symbol: {SYSTEM_CONFIG.TRADING_PAIR}")
    print(f"   Timeframe: {SYSTEM_CONFIG.PRIMARY_TIMEFRAME}")
    print(f"   Available candles: {candle_count}")
    
    # Load recent data
    df = fetcher.load_candles(limit=200)
    
    print(f"✅ Loaded {len(df)} candles")
    print(f"   Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Calculate features
    print("\n" + "=" * 60)
    df = calculate_all_features(df)
    
    # Validate
    print("\n" + "=" * 60)
    print("VALIDATION")
    print("=" * 60)
    
    all_valid, results = validate_all_features(df)
    
    for feature_type, result in results.items():
        status = "✅" if result['valid'] else "❌"
        print(f"{status} {feature_type.capitalize()}: {result['message']}")
    
    if not all_valid:
        print("\n❌ Feature validation failed!")
        return 1
    
    # Summary statistics
    print("\n" + "=" * 60)
    print("FEATURE SUMMARY")
    print("=" * 60)
    
    summary = get_feature_summary(df)
    
    if 'atr' in summary:
        print("\n📊 Volatility (ATR):")
        print(f"   Mean: ${summary['atr']['mean']:.2f}")
        print(f"   Mean %: {summary['atr']['mean_pct']:.2f}%")
        print(f"   Current: ${summary['atr']['current']:.2f}")
        print(f"   Percentile: {summary['atr']['percentile']:.1f}")
    
    if 'efficiency' in summary:
        print("\n📊 Trend Strength (Efficiency):")
        print(f"   Mean: {summary['efficiency']['mean']:.3f}")
        print(f"   Current: {summary['efficiency']['current']:.3f}")
        print(f"   Current strength: {summary['efficiency']['current_strength']}")
    
    if 'volume' in summary:
        print("\n📊 Volume:")
        print(f"   Mean: {summary['volume']['mean']:.2f}")
        print(f"   Current ratio: {summary['volume']['current_ratio']:.2f}x")
        print(f"   Current regime: {summary['volume']['current_regime']}")
        print(f"   Spikes detected: {summary['volume']['spikes_detected']}")
    
    # Export to CSV
    print("\n" + "=" * 60)
    print("EXPORT")
    print("=" * 60)
    
    # Create export directory
    os.makedirs('data/processed', exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    export_path = f'data/processed/features_{timestamp}.csv'
    
    export_features_csv(df, export_path)
    
    print(f"\n✅ Feature calculation complete")
    print(f"   Total features: {len(df.columns)}")
    print(f"   Exported to: {export_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())
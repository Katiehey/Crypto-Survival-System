"""
Analyze regime classifications on real market data.

This script:
1. Loads candle data
2. Calculates features and regimes
3. Displays regime statistics
4. Exports detailed regime analysis
"""

import os
from datetime import datetime
from data.fetcher import DataFetcher
from regime.features import calculate_complete_pipeline
from regime.classifier import get_regime_statistics


def main():
    """Analyze regimes on real market data."""
    print("=" * 60)
    print("REGIME ANALYSIS")
    print("=" * 60)
    
    # Load data
    fetcher = DataFetcher()
    candle_count = fetcher.get_candle_count()
    
    if candle_count == 0:
        print("\n❌ No data in database.")
        print("Run 'python data/fetcher.py' first to fetch data.")
        return 1
    
    print(f"\n📊 Loading candles from database...")
    df = fetcher.load_candles(limit=200)
    
    print(f"✅ Loaded {len(df)} candles")
    print(f"   Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Calculate complete pipeline
    try:
        df = calculate_complete_pipeline(df)
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        return 1
    
    # Get regime statistics
    stats = get_regime_statistics(df)
    
    print("\n" + "=" * 60)
    print("REGIME STATISTICS")
    print("=" * 60)
    
    print(f"\nTotal periods analyzed: {stats['total_periods']}")
    print(f"Tradable periods: {stats['tradable_periods']} ({stats['tradable_percentage']:.1f}%)")
    print(f"Mean confidence: {stats['mean_confidence']:.2f}")
    
    print("\n" + "-" * 60)
    print("REGIME DISTRIBUTION")
    print("-" * 60)
    
    for regime in ['trend', 'range', 'chaos', 'no_trade']:
        if regime in stats['regime_counts']:
            count = stats['regime_counts'][regime]
            pct = stats['regime_percentages'][regime]
            conf = stats['confidence_by_regime'].get(regime, 0)
            
            # Determine if tradable
            tradable_str = "✅" if regime in ['trend', 'range'] else "❌"
            
            print(f"{tradable_str} {regime.upper():10s}: {count:3d} periods ({pct:5.1f}%) - "
                  f"avg confidence: {conf:.2f}")
    
    # Current regime
    print("\n" + "-" * 60)
    print("CURRENT MARKET STATE")
    print("-" * 60)
    
    latest = df.iloc[-1]
    print(f"Current regime: {latest['regime'].upper()}")
    print(f"Confidence: {latest['regime_confidence']:.2f}")
    print(f"Tradable: {'Yes ✅' if latest['regime_tradable'] else 'No ❌'}")
    
    print(f"\nFeatures:")
    print(f"  Efficiency Ratio: {latest['efficiency_ratio']:.3f} ({latest['trend_strength']})")
    print(f"  ATR %ile: {latest['atr_percentile']:.1f}")
    print(f"  Volume regime: {latest['volume_regime']}")
    print(f"  Price: ${latest['close']:.2f}")
    
    # Show recent regime transitions
    print("\n" + "-" * 60)
    print("RECENT REGIMES (last 10 periods)")
    print("-" * 60)
    
    recent = df.tail(10)[[
        'datetime', 'close', 'regime', 'regime_confidence',
        'trend_strength', 'volume_regime'
    ]]
    
    print(recent.to_string(index=False))
    
    # Export detailed analysis
    print("\n" + "=" * 60)
    print("EXPORT")
    print("=" * 60)
    
    os.makedirs('data/processed', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    export_path = f'data/processed/regime_analysis_{timestamp}.csv'
    
    # Select columns for export
    export_cols = [
        'timestamp', 'datetime', 'close',
        'atr', 'atr_pct', 'atr_percentile',
        'efficiency_ratio', 'trend_strength',
        'volume_ratio', 'volume_regime',
        'regime', 'regime_confidence', 'regime_tradable'
    ]
    
    df[export_cols].to_csv(export_path, index=False)
    
    print(f"✅ Detailed analysis exported to: {export_path}")
    
    print("\n" + "=" * 60)
    print("✅ Regime analysis complete")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit(main())
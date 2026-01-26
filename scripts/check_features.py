import pandas as pd
import numpy as np
import logging
from backtest.data_loader import BacktestDataLoader

# Disable logging noise for cleaner output
logging.getLogger('data.fetcher').setLevel(logging.ERROR)

def diagnostic_check():
    print("🔍 Starting Feature Diagnostics...")
    
    # 1. Initialize Loader
    # It will automatically pull SYMBOL and TIMEFRAME from your SYSTEM_CONFIG
    loader = BacktestDataLoader()
    
    # 2. Load and Prepare (This runs the full pipeline including ER and Regimes)
    print(f"🔄 Loading and preparing data for {loader.symbol}...")
    try:
        # We'll load 1000 candles to see enough history for percentiles
        df = loader.load_and_prepare(limit=1000)
    except Exception as e:
        print(f"❌ Error during load_and_prepare: {e}")
        return

    # 3. Analyze Efficiency Ratio (ER)
    print("\n" + "="*45)
    print("📊 EFFICIENCY RATIO (ER) ANALYSIS")
    print("="*45)
    
    if 'efficiency_ratio' in df.columns:
        er_stats = df['efficiency_ratio'].describe()
        print(er_stats)
        
        zero_count = (df['efficiency_ratio'] == 0).sum()
        nan_count = df['efficiency_ratio'].isna().sum()
        print(f"\nEmpty (NaN) values:  {nan_count} (Normal for warmup)")
        print(f"Dead (0.0) values:   {zero_count}")
    else:
        print("❌ 'efficiency_ratio' column missing! Check regime/features.py")

    # 4. Analyze Regimes
    if 'regime' in df.columns:
        print("\n🎭 REGIME DISTRIBUTION")
        print(df['regime'].value_counts())
        
        # Check if we ever actually hit a "trend"
        trend_count = (df['regime'] == 'trend').sum()
        if trend_count == 0:
            print("\n⚠️  WARNING: Zero 'trend' regimes detected. The classifier is too strict.")
    
    # 5. Peek at the "Strategy View"
    # This is exactly what your strategy sees when making a decision
    print("\n👀 RECENT STRATEGY SNAPSHOT:")
    cols = ['datetime', 'close', 'efficiency_ratio', 'regime', 'regime_tradable']
    cols = [c for c in cols if c in df.columns]
    print(df[cols].tail(10).to_string(index=False))

    # 6. Final Verdict
    avg_er = df['efficiency_ratio'].mean() if 'efficiency_ratio' in df.columns else 0
    if avg_er > 0:
        print(f"\n✅ SUCCESS: Features are calculating. Average ER is {avg_er:.4f}")
    else:
        print("\n❌ FAILURE: Efficiency Ratio is not calculating correctly.")

if __name__ == "__main__":
    diagnostic_check()
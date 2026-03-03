#!/usr/bin/env python3
from paper_trading.data_provider import create_data_provider
from monitoring.psi import compute_baseline_quantiles, save_baseline
import numpy as np, os

def main():
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=5000)
    if 'regime' in df.columns:
        df = df.dropna(subset=['regime'])
        df['y'] = (df['regime']=='trend').astype(int)
    else:
        df['future_ret'] = df['close'].pct_change().shift(-6)
        df['y'] = (df['future_ret']>0).astype(int)

    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [c for c in numeric if c not in ('open','high','low','close','volume','regime','y','future_ret')]
    X = df[feature_cols].astype(float).fillna(0)
    split = int(len(X)*0.8)
    X_train = X.iloc[:split]

    baseline = {}
    for f in feature_cols:
        baseline[f] = compute_baseline_quantiles(X_train[f].astype(float).fillna(0), buckets=10)

    out = 'models/production/production_retrained_quantile/psi_baseline.json'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    save_baseline(baseline, out)
    print('Wrote', out)

if __name__ == '__main__':
    main()

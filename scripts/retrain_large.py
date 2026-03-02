#!/usr/bin/env python3
"""Retrain core-feature classifier on a larger history window.

Saves to `models/production/production_retrained_large`.
"""
import os
import json
import argparse
import datetime

import numpy as np
import pandas as pd

from paper_trading.data_provider import create_data_provider
from monitoring.psi import compute_baseline_quantiles, save_baseline


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=20000)
    args = p.parse_args()

    features = ['atr_pct','atr_percentile','efficiency_ratio','efficiency_ratio_smooth','efficiency_percentile','volume_ratio','volume_percentile']
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=args.limit)

    missing = [f for f in features if f not in df.columns]
    if missing:
        print('Missing features for large retrain:', missing)
        return False

    if 'regime' in df.columns:
        df['y'] = (df['regime'] == 'trend').astype(int)
    else:
        df['future_ret'] = df['close'].pct_change().shift(-6)
        df['y'] = (df['future_ret'] > 0).astype(int)

    X = df[features].astype(float).fillna(0)
    y = df['y'].fillna(0).astype(int)

    split = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split], X.iloc[split:]
    y_train, y_val = y.iloc[:split], y.iloc[split:]

    try:
        from sklearn.ensemble import RandomForestClassifier
        import joblib
    except Exception as e:
        print('ML deps missing:', e)
        return False

    clf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)
    val_acc = (clf.predict(X_val) == y_val).mean()

    out_dir = 'models/production/production_retrained_large'
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump(clf, os.path.join(out_dir, 'model.pkl'))

    meta = {'created_at': datetime.datetime.utcnow().isoformat() + 'Z', 'features': features, 'val_accuracy': float(val_acc), 'trained_on': int(len(X))}
    with open(os.path.join(out_dir, 'metadata.json'), 'w') as mf:
        json.dump(meta, mf, indent=2)

    baseline = {}
    for f in features:
        baseline[f] = compute_baseline_quantiles(X_train[f], buckets=10)
    save_baseline(baseline, os.path.join(out_dir, 'psi_baseline.json'))

    print('Wrote large candidate with val_acc=', val_acc)
    return True


if __name__ == '__main__':
    main()

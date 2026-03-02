#!/usr/bin/env python3
"""Retrain using the canonical feature set used by PSI diagnostics.

Features: ['atr_pct','atr_percentile','efficiency_ratio','efficiency_ratio_smooth',
'efficiency_percentile','volume_ratio','volume_percentile']
"""
import os
import json
import datetime

import numpy as np
import pandas as pd

from paper_trading.data_provider import create_data_provider
from monitoring.psi import compute_baseline_quantiles, save_baseline

def main():
    features = ['atr_pct','atr_percentile','efficiency_ratio','efficiency_ratio_smooth','efficiency_percentile','volume_ratio','volume_percentile']
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=5000)

    # ensure features present
    missing = [f for f in features if f not in df.columns]
    if missing:
        print('Missing features for core retrain:', missing)
        return False

    # build simple classifier target using regime vs not
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

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    val_acc = (clf.predict(X_val) == y_val).mean()

    out_dir = 'models/production/production_retrained_core'
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump(clf, os.path.join(out_dir, 'model.pkl'))

    meta = {'created_at': datetime.datetime.utcnow().isoformat() + 'Z', 'features': features, 'val_accuracy': float(val_acc)}
    with open(os.path.join(out_dir, 'metadata.json'), 'w') as mf:
        json.dump(meta, mf, indent=2)

    baseline = {}
    for f in features:
        baseline[f] = compute_baseline_quantiles(X_train[f], buckets=10)
    save_baseline(baseline, os.path.join(out_dir, 'psi_baseline.json'))

    print('Wrote candidate core model with val_acc=', val_acc)
    return True

if __name__ == '__main__':
    main()

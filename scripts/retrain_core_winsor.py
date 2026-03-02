#!/usr/bin/env python3
"""Retrain core-feature classifier with winsorization (clipping) to reduce outlier-driven PSI shifts.

Produces model under `models/production/production_retrained_core_winsor`.
"""
import os
import json
import datetime

import numpy as np
import pandas as pd

from paper_trading.data_provider import create_data_provider
from monitoring.psi import compute_baseline_quantiles, save_baseline


def winsorize_series(s, lower_p=0.01, upper_p=0.99):
    lo, hi = np.nanpercentile(s.dropna(), [100 * lower_p, 100 * upper_p])
    return s.clip(lo, hi)


def main():
    features = ['atr_pct','atr_percentile','efficiency_ratio','efficiency_ratio_smooth','efficiency_percentile','volume_ratio','volume_percentile']
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=5000)

    missing = [f for f in features if f not in df.columns]
    if missing:
        print('Missing features for winsor retrain:', missing)
        return False

    if 'regime' in df.columns:
        df['y'] = (df['regime'] == 'trend').astype(int)
    else:
        df['future_ret'] = df['close'].pct_change().shift(-6)
        df['y'] = (df['future_ret'] > 0).astype(int)

    X = df[features].astype(float).fillna(0)
    y = df['y'].fillna(0).astype(int)

    split = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split].copy(), X.iloc[split:].copy()
    y_train, y_val = y.iloc[:split], y.iloc[split:]

    # Apply winsorization per-feature based on training set
    for f in features:
        X_train[f] = winsorize_series(X_train[f], 0.01, 0.99)
        X_val[f] = winsorize_series(X_val[f], 0.01, 0.99)

    try:
        from sklearn.ensemble import RandomForestClassifier
        import joblib
    except Exception as e:
        print('ML deps missing:', e)
        return False

    clf = RandomForestClassifier(n_estimators=200, random_state=42)
    clf.fit(X_train, y_train)
    val_acc = (clf.predict(X_val) == y_val).mean()

    out_dir = 'models/production/production_retrained_core_winsor'
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump(clf, os.path.join(out_dir, 'model.pkl'))

    meta = {'created_at': datetime.datetime.utcnow().isoformat() + 'Z', 'features': features, 'val_accuracy': float(val_acc), 'preprocessing': 'winsorize(1%,99%)'}
    with open(os.path.join(out_dir, 'metadata.json'), 'w') as mf:
        json.dump(meta, mf, indent=2)

    baseline = {}
    for f in features:
        baseline[f] = compute_baseline_quantiles(X_train[f], buckets=10)
    save_baseline(baseline, os.path.join(out_dir, 'psi_baseline.json'))

    print('Wrote winsorized candidate core model with val_acc=', val_acc)
    return True


if __name__ == '__main__':
    main()

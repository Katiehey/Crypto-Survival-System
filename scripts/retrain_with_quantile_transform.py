#!/usr/bin/env python3
"""Retrain candidate model using QuantileTransformer to stabilize feature distributions.

Saves pipeline to `models/production/production_retrained_quantile` with:
- model.pkl (joblib pipeline)
- metadata.json
- psi_baseline.json (computed from transformed training features)
"""
import os
import json
import datetime

import numpy as np
import pandas as pd

from paper_trading.data_provider import create_data_provider
from monitoring.psi import compute_baseline_quantiles, save_baseline


def train_and_save(candidate_dir='models/production/production_retrained_quantile'):
    os.makedirs(candidate_dir, exist_ok=True)

    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=5000)

    if 'regime' in df.columns:
        df = df.dropna(subset=['regime'])
        df['y'] = (df['regime'] == 'trend').astype(int)
    else:
        df['future_ret'] = df['close'].pct_change().shift(-6)
        df['y'] = (df['future_ret'] > 0).astype(int)

    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [c for c in numeric if c not in ('open','high','low','close','volume','regime','y','future_ret')]
    X = df[feature_cols].astype(float).fillna(0)
    y = df['y'].fillna(0).astype(int)

    split = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split], X.iloc[split:]
    y_train, y_val = y.iloc[:split], y.iloc[split:]

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import QuantileTransformer
        from sklearn.pipeline import Pipeline
        import joblib
    except Exception as e:
        print('ML deps missing:', e)
        return False

    pipeline = Pipeline([
        ('quantile', QuantileTransformer(output_distribution='uniform', random_state=42)),
        ('clf', RandomForestClassifier(n_estimators=200, random_state=42))
    ])

    pipeline.fit(X_train, y_train)

    val_pred = pipeline.predict(X_val)
    acc = (val_pred == y_val).mean()

    model_path = os.path.join(candidate_dir, 'model.pkl')
    joblib.dump(pipeline, model_path)

    meta = {
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'source': 'retrain_with_quantile_transform.py',
        'val_accuracy': float(acc),
        'feature_count': len(feature_cols),
        'features': feature_cols[:200]
    }
    with open(os.path.join(candidate_dir, 'metadata.json'), 'w') as mf:
        json.dump(meta, mf, indent=2)

    # compute baseline from transformed training features
    transformed = pipeline.named_steps['quantile'].transform(X_train)
    baseline = {}
    for idx, f in enumerate(feature_cols):
        col_series = pd.Series(transformed[:, idx])
        baseline[f] = compute_baseline_quantiles(col_series.fillna(0), buckets=10)
    save_baseline(baseline, os.path.join(candidate_dir, 'psi_baseline.json'))

    os.makedirs('backtest_results/retrain_quantile', exist_ok=True)
    with open('backtest_results/retrain_quantile/validation.json', 'w') as vf:
        json.dump({'val_accuracy': acc, 'meta': meta}, vf, indent=2)

    print('Trained quantile-transform candidate, val_acc=', acc)
    return True


if __name__ == '__main__':
    train_and_save()

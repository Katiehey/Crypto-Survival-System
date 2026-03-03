#!/usr/bin/env python3
"""Train a candidate model on recent data and save under models/production/production_retrained_candidate

This is a fast prototyping retrain: uses RandomForestClassifier on features produced by
the `paper_trading.data_provider` pipeline. Produces:
- models/production/production_retrained_candidate/model.pkl
- models/production/production_retrained_candidate/metadata.json
- models/production/production_retrained_candidate/psi_baseline.json
and writes validation metrics to backtest_results/retrain_candidate/
"""
import os
import json
from glob import glob
import datetime

import numpy as np
import pandas as pd

from paper_trading.data_provider import create_data_provider
from monitoring.psi import compute_baseline_quantiles, save_baseline

def train_and_save(candidate_dir='models/production/production_retrained_candidate'):
    os.makedirs(candidate_dir, exist_ok=True)

    # Load recent historical features
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=5000)

    # Prepare features and a synthetic target: use regime label as proxy (trend vs not)
    if 'regime' in df.columns:
        df = df.dropna(subset=['regime'])
        df['y'] = (df['regime'] == 'trend').astype(int)
    else:
        # fallback: create a target from future returns
        df['future_ret'] = df['close'].pct_change().shift(-6)
        df['y'] = (df['future_ret'] > 0).astype(int)

    # use only numeric columns as features
    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [c for c in numeric if c not in ('open','high','low','close','volume','regime','y','future_ret')]
    X = df[feature_cols].astype(float).fillna(0)
    y = df['y'].fillna(0).astype(int)

    # train/test split
    split = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split], X.iloc[split:]
    y_train, y_val = y.iloc[:split], y.iloc[split:]

    # train a RandomForestClassifier
    try:
        from sklearn.ensemble import RandomForestClassifier
        import joblib
    except Exception as e:
        print('ML deps missing:', e)
        return False

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)

    # validation
    val_pred = clf.predict(X_val)
    acc = (val_pred == y_val).mean()

    # save model
    model_path = os.path.join(candidate_dir, 'model.pkl')
    joblib.dump(clf, model_path)

    meta = {
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'source': 'retrain_candidate_model.py',
        'val_accuracy': float(acc),
        'feature_count': len(feature_cols),
        'features': feature_cols[:200]
    }
    with open(os.path.join(candidate_dir, 'metadata.json'), 'w') as mf:
        json.dump(meta, mf, indent=2)

    # compute baseline from training features
    baseline = {}
    for f in feature_cols:
        baseline[f] = compute_baseline_quantiles(X_train[f].astype(float).fillna(0), buckets=10)
    save_baseline(baseline, os.path.join(candidate_dir, 'psi_baseline.json'))

    # write validation summary
    os.makedirs('backtest_results/retrain_candidate', exist_ok=True)
    with open('backtest_results/retrain_candidate/validation.json', 'w') as vf:
        json.dump({'val_accuracy': acc, 'meta': meta}, vf, indent=2)

    print('Trained candidate model, val_acc=', acc)
    return True

if __name__ == '__main__':
    train_and_save()

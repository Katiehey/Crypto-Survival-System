"""
Train a lightweight ML model (smoke test) using features CSV.
- If scikit-learn is not available, prints instructions and exits cleanly.

Usage:
    PYTHONPATH=. python3 scripts/train_model.py --features data/processed/features_sample.csv --out models/smoke
"""
import argparse
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime


def train_smoke(features_csv: str, out_dir: str):
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import roc_auc_score, accuracy_score
    except Exception as e:
        print("scikit-learn not available. Install it with: pip install scikit-learn")
        return 2

    df = pd.read_csv(features_csv)
    # Drop rows with NaNs in target or key features
    df = df.dropna(subset=['target_up', 'close'])

    feature_cols = [
        'atr_pct', 'atr_percentile', 'efficiency_ratio', 'efficiency_ratio_smooth',
        'efficiency_percentile', 'volume_ratio', 'volume_percentile'
    ]
    feature_cols = [c for c in feature_cols if c in df.columns]

    if len(feature_cols) == 0:
        print("No feature columns found in CSV. Run scripts/ml_features.py first.")
        return 3

    X = df[feature_cols].fillna(0)
    y = df['target_up'].astype(int)

    # Simple train/test split for smoke
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    clf = RandomForestClassifier(n_estimators=50, max_depth=6, random_state=42)
    clf.fit(X_train, y_train)

    preds = clf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, preds)
    acc = accuracy_score(y_test, (preds > 0.5).astype(int))

    # Save model artefacts
    os.makedirs(out_dir, exist_ok=True)
    model_path = os.path.join(out_dir, 'model.pkl')
    metadata_path = os.path.join(out_dir, 'metadata.json')

    try:
        import joblib
        joblib.dump(clf, model_path)
    except Exception:
        # fallback to pickle
        import pickle
        with open(model_path, 'wb') as f:
            pickle.dump(clf, f)

    metadata = {
        'created_at': datetime.utcnow().isoformat(),
        'features': feature_cols,
        'auc': float(auc),
        'accuracy': float(acc),
        'n_samples': int(len(df)),
    }

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Trained model saved to {out_dir}")
    print(f"   AUC: {auc:.4f}, Acc: {acc:.4f}, Samples: {len(df)}")
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--features', type=str, default='data/processed/features_sample.csv')
    p.add_argument('--out', type=str, default='models/smoke')
    args = p.parse_args()
    code = train_smoke(args.features, args.out)
    raise SystemExit(code)

"""
Train walk-forward models across folds and save model artefacts.
Usage:
    PYTHONPATH=. python3 scripts/train_walkforward_models.py --folds 3
"""
import os
import json
import argparse
from datetime import datetime

import pandas as pd

from config.system_config import SYSTEM_CONFIG
from regime.features import calculate_complete_pipeline


def load_candles(db_path: str, limit: int = None):
    import sqlite3
    conn = sqlite3.connect(db_path)
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM candles
        ORDER BY timestamp ASC
    """
    if limit:
        query = query.replace('ORDER BY timestamp ASC', f'ORDER BY timestamp ASC LIMIT {limit}')
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


def prepare_features(df: pd.DataFrame):
    dff = calculate_complete_pipeline(df)
    dff['ret_1'] = dff['close'].pct_change().shift(-1)
    dff['target_up'] = (dff['ret_1'] > 0).astype(int)
    return dff


def train_fold(X_train, y_train):
    from sklearn.ensemble import RandomForestClassifier
    clf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    clf.fit(X_train, y_train)
    return clf


def evaluate(clf, X_test, y_test):
    from sklearn.metrics import roc_auc_score, accuracy_score
    probs = clf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else None
    acc = accuracy_score(y_test, (probs > 0.5).astype(int))
    return auc, acc


def main(folds: int = 3, train_window: int = 1000, test_window: int = 500, step: int = 250, out_dir: str = 'models/walkforward'):
    os.makedirs(out_dir, exist_ok=True)

    df = load_candles(SYSTEM_CONFIG.DB_PATH, limit=(train_window + test_window + (folds-1)*step))
    if df.empty:
        raise RuntimeError('No candles available for training')

    # Prepare features once
    df_feat = calculate_complete_pipeline(df)
    df_feat['ret_1'] = df_feat['close'].pct_change().shift(-1)
    df_feat['target_up'] = (df_feat['ret_1'] > 0).astype(int)

    feature_cols = [
        'atr_pct', 'atr_percentile', 'efficiency_ratio', 'efficiency_ratio_smooth',
        'efficiency_percentile', 'volume_ratio', 'volume_percentile'
    ]

    rows = []
    n = len(df_feat)
    # Compute how many folds are actually possible with the data available
    max_folds = max(0, (n - train_window - test_window) // step + 1)
    if max_folds <= 0:
        # Fallback: shrink windows proportionally to available data
        train_window = int(n * 0.6)
        test_window = int(n * 0.2)
        step = max(1, int(n * 0.1))
        max_folds = max(0, (n - train_window - test_window) // step + 1)

    effective_folds = min(folds, max_folds if max_folds > 0 else folds)

    for i in range(effective_folds):
        train_start = i * step
        train_end = train_start + train_window
        test_end = train_end + test_window
        if test_end > n:
            # If this fold cannot fit, skip
            print(f'Skipping fold {i}: insufficient data for train_end/test_end ({train_end}/{test_end})')
            continue

        train_df = df_feat.iloc[train_start:train_end].dropna(subset=['target_up', 'close'])
        test_df = df_feat.iloc[train_end:test_end].dropna(subset=['target_up', 'close'])

        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df['target_up'].astype(int)
        X_test = test_df[feature_cols].fillna(0)
        y_test = test_df['target_up'].astype(int)

        if len(X_train) < 10 or len(X_test) < 10:
            print(f'Skipping fold {i}: insufficient data (train {len(X_train)}, test {len(X_test)})')
            continue

        clf = train_fold(X_train, y_train)
        auc, acc = evaluate(clf, X_test, y_test)

        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        model_dir = os.path.join(out_dir, f'{ts}_fold{i}')
        os.makedirs(model_dir, exist_ok=True)

        model_path = os.path.join(model_dir, 'model.pkl')
        try:
            import joblib
            joblib.dump(clf, model_path)
        except Exception:
            import pickle
            with open(model_path, 'wb') as f:
                pickle.dump(clf, f)

        metadata = {
            'created_at': datetime.utcnow().isoformat(),
            'fold': i,
            'features': feature_cols,
            'auc': auc,
            'accuracy': acc,
            'n_train': int(len(X_train)),
            'n_test': int(len(X_test))
        }
        with open(os.path.join(model_dir, 'metadata.json'), 'w') as mf:
            json.dump(metadata, mf, indent=2)

        rows.append({
            'fold': i,
            'model_dir': model_dir,
            'auc': auc,
            'accuracy': acc,
            'n_train': len(X_train),
            'n_test': len(X_test)
        })

        print(f'Trained fold {i}: AUC={auc}, ACC={acc}, model saved to {model_dir}')

    out_csv = os.path.join(out_dir, 'walkforward_summary.csv')
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f'Walk-forward training complete. Summary: {out_csv}')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--folds', type=int, default=3)
    p.add_argument('--train_window', type=int, default=1000)
    p.add_argument('--test_window', type=int, default=500)
    p.add_argument('--step', type=int, default=250)
    args = p.parse_args()
    main(folds=args.folds, train_window=args.train_window, test_window=args.test_window, step=args.step)

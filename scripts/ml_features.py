"""
Extract and persist features for ML prototypes.
Usage:
    PYTHONPATH=. python3 scripts/ml_features.py --limit 500 --out data/processed/features_sample.csv
"""
import argparse
import os
import sqlite3
import pandas as pd

from config.system_config import SYSTEM_CONFIG
from regime.features import calculate_complete_pipeline


def load_candles_from_db(db_path: str, symbol: str = None, timeframe: str = None, limit: int = None) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM candles
        WHERE 1=1
    """
    params = []
    if symbol:
        query += " AND symbol = ?"
        params.append(symbol)
    if timeframe:
        query += " AND timeframe = ?"
        params.append(timeframe)
    query += " ORDER BY timestamp DESC"
    if limit:
        query += f" LIMIT {limit}"

    df = pd.read_sql_query(query, conn, params=tuple(params))
    conn.close()

    if df.empty:
        raise RuntimeError(f"No candles found in DB: {db_path}")

    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


def main(limit: int, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    db_path = SYSTEM_CONFIG.DB_PATH
    df = load_candles_from_db(db_path, limit=limit)

    # Run feature pipeline
    df_feat = calculate_complete_pipeline(df)

    # Add simple target: next period return
    df_feat['ret_1'] = df_feat['close'].pct_change().shift(-1)
    df_feat['target_up'] = (df_feat['ret_1'] > 0).astype(int)

    # Save a subset of useful columns
    cols = [
        'datetime', 'open', 'high', 'low', 'close', 'volume',
        'atr', 'atr_pct', 'atr_percentile',
        'efficiency_ratio', 'efficiency_ratio_smooth', 'efficiency_percentile',
        'volume_ratio', 'volume_percentile', 'volume_spike',
        'regime', 'regime_confidence', 'regime_tradable',
        'ret_1', 'target_up'
    ]
    cols_to_save = [c for c in cols if c in df_feat.columns]

    df_feat[cols_to_save].to_csv(out_path, index=False)
    print(f"✅ Features written to {out_path}")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=1000, help='Number of candles to load')
    p.add_argument('--out', dest='out_path', type=str, default='data/processed/features_sample.csv')
    args = p.parse_args()
    main(args.limit, args.out_path)

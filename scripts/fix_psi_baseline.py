"""Fix or regenerate missing feature quantiles in the PSI baseline for the latest production model.

Usage: PYTHONPATH=. python3 scripts/fix_psi_baseline.py
"""
import os
import json
from glob import glob

from monitoring.psi import compute_baseline_quantiles, save_baseline

def find_latest_production_model(base_dir='models/production'):
    dirs = sorted(glob(os.path.join(base_dir, '*')))
    if not dirs:
        raise FileNotFoundError('No production models found')
    return dirs[-1]

def main():
    try:
        model_dir = find_latest_production_model()
    except Exception as e:
        print('No production model found:', e)
        return 1

    baseline_file = os.path.join(model_dir, 'psi_baseline.json')
    print('Model dir:', model_dir)
    print('Baseline file:', baseline_file)

    # Load ML feature list if available
    try:
        from paper_trading.ml_inference import MLInference
        mi = MLInference(model_path=os.path.join(model_dir, 'model.pkl'))
        features = getattr(mi, 'feature_names', []) or []
    except Exception as e:
        print('Failed to load MLInference:', e)
        features = []

    # If no features, try to read an existing baseline and print keys
    if not features and os.path.exists(baseline_file):
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        print('Baseline keys:', list(baseline.keys()))
        return 0

    # Load or create baseline dict
    baseline = {}
    if os.path.exists(baseline_file):
        try:
            with open(baseline_file, 'r') as f:
                baseline = json.load(f)
        except Exception as e:
            print('Failed to load baseline, regenerating:', e)
            baseline = {}

    # Prepare historical data provider
    from paper_trading.data_provider import create_data_provider
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=2000)

    for f in features:
        if f in baseline and isinstance(baseline[f], list) and len(baseline[f])>0:
            continue
        # skip obvious time/index
        lf = f.lower()
        if ('time' in lf) or (lf in ('timestamp','index')):
            baseline[f] = []
            continue
        if f not in df.columns:
            print('Feature not present in historical data, skipping:', f)
            baseline[f] = []
            continue
        print('Computing baseline quantiles for', f)
        try:
            q = compute_baseline_quantiles(df[f].iloc[:1000], buckets=10)
            baseline[f] = q
        except Exception as e:
            print('Failed to compute quantiles for', f, e)
            baseline[f] = []

    # Save baseline
    try:
        save_baseline(baseline, baseline_file)
        print('Saved baseline to', baseline_file)
    except Exception as e:
        print('Failed to save baseline:', e)
        return 1

    return 0

if __name__ == '__main__':
    exit(main())

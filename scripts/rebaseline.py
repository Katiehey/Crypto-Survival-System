#!/usr/bin/env python3
"""Generate a PSI baseline for a production model directory.

Usage:
  python scripts/rebaseline.py --model-dir models/production/... [--buckets 10] [--commit]

If --commit is passed, the script will git add/commit/push the generated baseline.
"""
import argparse
import json
import os
import sys
import pathlib

project_root = pathlib.Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from monitoring.psi import compute_baseline_quantiles, save_baseline
from paper_trading.data_provider import create_data_provider


def find_latest_model(base_dir='models/production'):
    import glob
    dirs = sorted(glob.glob(os.path.join(base_dir, '*')))
    if not dirs:
        raise FileNotFoundError('No production models found')
    return dirs[-1]


def build_baseline(model_dir, buckets=10, limit=2000):
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=limit)
    baseline = {}
    for col in df.columns:
        lowname = col.lower()
        # Skip obvious non-numeric/time columns
        if ('time' in lowname) or lowname in ('timestamp', 'index'):
            baseline[col] = []
            continue
        try:
            import pandas as pd
            if not pd.api.types.is_numeric_dtype(df[col]):
                baseline[col] = []
                continue
        except Exception:
            baseline[col] = []
            continue
        try:
            baseline[col] = compute_baseline_quantiles(df[col].iloc[:1000], buckets=buckets)
        except Exception:
            baseline[col] = []
    return baseline


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', default=None)
    p.add_argument('--buckets', type=int, default=10)
    p.add_argument('--commit', action='store_true')
    args = p.parse_args()

    model_dir = args.model_dir or find_latest_model()
    if not os.path.isdir(model_dir):
        print('Model dir not found:', model_dir)
        sys.exit(1)

    print('Building baseline for', model_dir)
    baseline = build_baseline(model_dir, buckets=args.buckets)
    out_path = os.path.join(model_dir, 'psi_baseline.json')
    save_baseline(baseline, out_path)
    print('Saved baseline to', out_path)

    if args.commit:
        try:
            import subprocess
            subprocess.check_call(['git', 'add', out_path])
            subprocess.check_call(['git', 'commit', '-m', f'rebaseline: update psi_baseline.json for {os.path.basename(model_dir)}'],)
            subprocess.check_call(['git', 'push', 'origin', 'HEAD:main'])
            print('Committed and pushed baseline')
        except Exception as e:
            print('Failed to commit/push baseline:', e)


if __name__ == '__main__':
    main()

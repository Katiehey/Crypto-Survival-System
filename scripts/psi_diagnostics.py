#!/usr/bin/env python3
"""Generate PSI diagnostics for multiple windows and save summaries + plots.

Outputs to `backtest_results/psi_diagnostics/{window}d/` with:
- `psi_summary.json` (per-feature PSI and status)
- `{feature}.png` histograms (expected vs actual)
"""
import os
import json
from glob import glob
from monitoring.psi import calculate_psi, compute_baseline_quantiles, save_baseline, load_baseline
from paper_trading.data_provider import create_data_provider
from paper_trading.ml_inference import MLInference
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import argparse


def find_latest_production_model(base_dir='models/production'):
    dirs = sorted(glob(os.path.join(base_dir, '*')))
    if not dirs:
        raise FileNotFoundError('No production models found')
    return dirs[-1]


def synth_expected_from_quantiles(quantiles, samples_per_bin=100):
    expected = []
    for i in range(len(quantiles)-1):
        a, b = quantiles[i], quantiles[i+1]
        if np.isclose(a, b):
            expected.extend([a] * samples_per_bin)
        else:
            expected.extend(list(a + (b - a) * np.random.rand(samples_per_bin)))
    return pd.Series(expected)


def run_diagnostics(windows_days=(7,14,30,90), out_root='backtest_results/psi_diagnostics'):
    model_dir = find_latest_production_model()
    model_path = os.path.join(model_dir, 'model.pkl')

    # Try to get feature names from model if possible
    try:
        mi = MLInference(model_path=model_path)
        features = getattr(mi, 'feature_names', []) or []
    except Exception:
        features = []

    # Fallback: attempt to infer features from a recent feature run
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=2500)

    if not features:
        # pick numeric columns that look like features
        candidates = [c for c in df.columns if df[c].dtype.kind in 'fiu']
        features = [c for c in candidates if c not in ('open','high','low','close','volume')][:20]

    # Load or compute baseline per feature
    baseline_file = os.path.join(model_dir, 'psi_baseline.json')
    if os.path.exists(baseline_file):
        baseline = load_baseline(baseline_file)
    else:
        baseline = {}
        for f in features:
            baseline[f] = compute_baseline_quantiles(df[f].iloc[:1000], buckets=10)
        save_baseline(baseline, baseline_file)

    os.makedirs(out_root, exist_ok=True)

    for days in windows_days:
        hours = days * 24
        out_dir = os.path.join(out_root, f'{days}d')
        os.makedirs(out_dir, exist_ok=True)
        recent = df[features].iloc[-hours:]

        psi_results = {}
        for f in features:
            quantiles = np.array(baseline.get(f, []))
            if len(quantiles) < 2:
                psi_results[f] = {'psi': None, 'status': 'NO_BASELINE'}
                continue

            expected = synth_expected_from_quantiles(quantiles, samples_per_bin=200)
            try:
                psi_val, details = calculate_psi(expected=expected, actual=recent[f].dropna(), buckets=10)
            except Exception as e:
                psi_val, details = None, f'error:{e}'

            status = ('DATA_ISSUE' if psi_val is None else ('OK' if psi_val < 0.1 else ('WARN' if psi_val < 0.25 else 'ALERT')))
            psi_results[f] = {'psi': psi_val, 'status': status, 'detail': details}

            # Plot expected vs actual histogram
            try:
                edges = quantiles
                actual_vals = recent[f].dropna()
                plt.figure(figsize=(6,4))
                plt.hist(expected, bins=edges, alpha=0.5, label='expected')
                plt.hist(actual_vals, bins=edges, alpha=0.5, label='actual')
                plt.legend()
                plt.title(f'{f} — PSI={psi_val}')
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, f'{f}.png'))
                plt.close()
            except Exception:
                pass

        # Save summary
        summary_path = os.path.join(out_dir, 'psi_summary.json')
        with open(summary_path, 'w') as fo:
            json.dump(psi_results, fo, default=str, indent=2)

    print('Diagnostics written to', out_root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--windows', default='7,14,30,90', help='Comma-separated days')
    parser.add_argument('--out-root', default='backtest_results/psi_diagnostics')
    args = parser.parse_args()
    windows = [int(x) for x in args.windows.split(',') if x.strip()]
    run_diagnostics(windows_days=windows, out_root=args.out_root)

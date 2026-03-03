#!/usr/bin/env python3
"""Recompute model baseline from recent production-like data and produce comparison plots.

Outputs to `backtest_results/psi_rebaseline/`:
- `comparison_summary.json` (per-feature old_baseline, new_baseline, psi_old, psi_new)
- `{feature}_old_vs_actual.png`, `{feature}_new_vs_actual.png`, `{feature}_baseline_overlay.png`
"""
import os
import json
from glob import glob
from monitoring.psi import compute_baseline_quantiles, save_baseline, load_baseline, calculate_psi
from paper_trading.data_provider import create_data_provider
from paper_trading.ml_inference import MLInference
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def find_latest_production_model(base_dir='models/production'):
    dirs = sorted(glob(os.path.join(base_dir, '*')))
    if not dirs:
        raise FileNotFoundError('No production models found')
    return dirs[-1]


def synth_expected_from_quantiles(quantiles, samples_per_bin=200):
    vals = []
    for i in range(len(quantiles)-1):
        a, b = quantiles[i], quantiles[i+1]
        if np.isclose(a, b):
            vals.extend([a] * samples_per_bin)
        else:
            vals.extend(list(a + (b - a) * np.random.rand(samples_per_bin)))
    return pd.Series(vals)


def main(out_root='backtest_results/psi_rebaseline', baseline_window=2000, baseline_buckets=10):
    os.makedirs(out_root, exist_ok=True)
    model_dir = find_latest_production_model()
    baseline_file = os.path.join(model_dir, 'psi_baseline.json')

    # Load old baseline if exists
    old_baseline = None
    if os.path.exists(baseline_file):
        try:
            old_baseline = load_baseline(baseline_file)
        except Exception:
            old_baseline = None

    # load recent data
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=baseline_window + 500)

    # try to get feature names from model
    try:
        mi = MLInference(model_path=os.path.join(model_dir, 'model.pkl'))
        features = getattr(mi, 'feature_names', []) or []
    except Exception:
        features = []

    if not features:
        candidates = [c for c in df.columns if df[c].dtype.kind in 'fiu']
        features = [c for c in candidates if c not in ('open','high','low','close','volume')][:20]

    # compute new baseline from most recent `baseline_window` rows
    new_baseline = {}
    for f in features:
        ser = df[f].dropna()
        if len(ser) < baseline_buckets:
            new_baseline[f] = []
            continue
        new_baseline[f] = compute_baseline_quantiles(ser.iloc[-baseline_window:], buckets=baseline_buckets)

    # Save new baseline to a file (not overwriting existing baseline)
    new_baseline_file = os.path.join(out_root, 'psi_baseline_recomputed.json')
    with open(new_baseline_file, 'w') as fo:
        json.dump(new_baseline, fo, default=str, indent=2)

    summary = {}
    recent_actual = df[features].iloc[-200:]

    for f in features:
        entry = {}
        entry['old_baseline'] = old_baseline.get(f) if old_baseline else None
        entry['new_baseline'] = new_baseline.get(f)

        # compute psi between old baseline (synth) and recent actual
        if entry['old_baseline']:
            expected_old = synth_expected_from_quantiles(np.array(entry['old_baseline']), samples_per_bin=200)
            psi_old, detail_old = calculate_psi(expected=expected_old, actual=recent_actual[f].dropna(), buckets=baseline_buckets)
        else:
            psi_old, detail_old = None, 'no_old_baseline'

        # compute psi between new baseline synth and recent actual
        if entry['new_baseline']:
            expected_new = synth_expected_from_quantiles(np.array(entry['new_baseline']), samples_per_bin=200)
            psi_new, detail_new = calculate_psi(expected=expected_new, actual=recent_actual[f].dropna(), buckets=baseline_buckets)
        else:
            psi_new, detail_new = None, 'no_new_baseline'

        entry['psi_old'] = psi_old
        entry['psi_new'] = psi_new
        entry['detail_old'] = detail_old
        entry['detail_new'] = detail_new

        # produce plots
        try:
            out_old = os.path.join(out_root, f'{f}_old_vs_actual.png')
            out_new = os.path.join(out_root, f'{f}_new_vs_actual.png')
            out_overlay = os.path.join(out_root, f'{f}_baseline_overlay.png')

            if entry['old_baseline']:
                plt.figure(figsize=(6,4))
                plt.hist(expected_old, bins=np.array(entry['old_baseline']), alpha=0.6, label='expected_old')
                plt.hist(recent_actual[f].dropna(), bins=np.array(entry['old_baseline']), alpha=0.4, label='actual')
                plt.legend()
                plt.title(f'{f} old baseline vs actual — psi_old={psi_old}')
                plt.savefig(out_old)
                plt.close()

            if entry['new_baseline']:
                plt.figure(figsize=(6,4))
                plt.hist(expected_new, bins=np.array(entry['new_baseline']), alpha=0.6, label='expected_new')
                plt.hist(recent_actual[f].dropna(), bins=np.array(entry['new_baseline']), alpha=0.4, label='actual')
                plt.legend()
                plt.title(f'{f} new baseline vs actual — psi_new={psi_new}')
                plt.savefig(out_new)
                plt.close()

            # overlay quantile lines
            if entry['old_baseline'] and entry['new_baseline']:
                plt.figure(figsize=(8,2))
                old_q = np.array(entry['old_baseline'])
                new_q = np.array(entry['new_baseline'])
                y1 = np.ones_like(old_q) * 0.6
                y2 = np.ones_like(new_q) * 0.4
                plt.plot(old_q, y1, 'r.-', label='old quantiles')
                plt.plot(new_q, y2, 'b.-', label='new quantiles')
                plt.yticks([])
                plt.legend()
                plt.title(f'{f} baseline quantile overlay')
                plt.savefig(out_overlay)
                plt.close()
        except Exception:
            pass

        summary[f] = entry

    summary_path = os.path.join(out_root, 'comparison_summary.json')
    with open(summary_path, 'w') as fo:
        json.dump(summary, fo, default=str, indent=2)

    print('Recomputed baseline and wrote comparison to', out_root)


if __name__ == '__main__':
    main()

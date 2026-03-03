#!/usr/bin/env python3
"""Recompute PSI baseline preferring smoothed/percentile features.

This creates `psi_baseline.json` in the specified model dir and a copy in
`backtest_results/psi_rebaseline/psi_baseline_recomputed.json` for comparison.
"""
import os
import json
import argparse
from monitoring.psi import compute_baseline_quantiles
from paper_trading.data_provider import create_data_provider


def preferred_columns(cols):
    # prefer *_smooth_percentile -> *_percentile -> *_smooth -> raw
    pref = []
    seen = set()
    for c in cols:
        seen.add(c)
    for c in cols:
        base = c
    # build candidate mapping later
    return cols


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', required=True)
    p.add_argument('--baseline-window', type=int, default=2000)
    args = p.parse_args()

    # load recent data
    prov = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = prov.get_historical_data(limit=args.baseline_window + 500)

    features = [c for c in df.columns if df[c].dtype.kind in 'fiu']

    # We'll prefer smoothed or percentile variants when available.
    # Build final list of feature names to compute baselines for.
    final_features = set()
    for f in features:
        # prefer percentile-smoothed
        if f + '_smooth_percentile' in df.columns:
            final_features.add(f + '_smooth_percentile')
        elif f + '_percentile' in df.columns:
            final_features.add(f + '_percentile')
        elif f + '_smooth' in df.columns:
            final_features.add(f + '_smooth')
        else:
            final_features.add(f)

    final_features = sorted(list(final_features))

    baseline = {}
    for f in final_features:
        ser = df[f].dropna() if f in df.columns else None
        if ser is None or len(ser) < 10:
            baseline[f] = []
            continue
        baseline[f] = compute_baseline_quantiles(ser.iloc[-args.baseline_window:], buckets=10)

    # write to model dir
    os.makedirs(args.model_dir, exist_ok=True)
    model_path = os.path.join(args.model_dir, 'psi_baseline.json')
    with open(model_path, 'w') as fo:
        json.dump(baseline, fo, indent=2)

    # also save to backtest_results for inspection
    os.makedirs('backtest_results/psi_rebaseline', exist_ok=True)
    out = 'backtest_results/psi_rebaseline/psi_baseline_recomputed.json'
    with open(out, 'w') as fo:
        json.dump(baseline, fo, indent=2)

    print('Wrote recomputed baseline to', model_path)

if __name__ == '__main__':
    main()

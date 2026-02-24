"""Run a PSI (Population Stability Index) check between a stored baseline
and recent feature values for the production model.

This is a lightweight skeleton that:
- finds the latest production model directory
- loads features via `paper_trading.ml_inference.MLInference`
- pulls historical data (historical provider) which runs feature pipeline
- computes/creates a baseline (saved under the model folder)
- computes PSI per feature and prints a summary
"""
import os
import json
from glob import glob
from monitoring.psi import calculate_psi, compute_baseline_quantiles, save_baseline, load_baseline

import numpy as np
import pandas as pd

from paper_trading.ml_inference import MLInference
from paper_trading.data_provider import create_data_provider
from monitoring.psi import run_model_psi_check
from monitoring.alerts import send_telegram_alert
import sys


def find_latest_production_model(base_dir='models/production'):
    dirs = sorted(glob(os.path.join(base_dir, '*')))
    if not dirs:
        raise FileNotFoundError('No production models found')
    return dirs[-1]


def main():
    model_dir = find_latest_production_model()
    model_path = os.path.join(model_dir, 'model.pkl')
    meta_path = os.path.join(model_dir, 'metadata.json')

    # Guard ML model loading in CI (sklearn may not be installed on runners)
    try:
        mi = MLInference(model_path=model_path)
    except ModuleNotFoundError as e:
        print('ML dependencies not available; skipping PSI model-based check:', e)
        # Write empty result file so CI step downstream can continue
        out_path = os.path.join(model_dir, 'psi_check.json')
        with open(out_path, 'w') as fo:
            json.dump({}, fo)
        print('Wrote', out_path)
        return
    features = mi.feature_names
    if not features:
        print('Model does not expose feature names; cannot run PSI')
        return

    # Load historical data (provider will compute features)
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=2000)

    # Ensure features exist in df
    missing = [f for f in features if f not in df.columns]
    if missing:
        print(f'Missing feature columns in historical data: {missing}')
        return

    baseline_file = os.path.join(model_dir, 'psi_baseline.json')
    if not os.path.exists(baseline_file):
        print('Baseline not found — creating from historical sample')
        baseline = {}
        for f in features:
            baseline[f] = compute_baseline_quantiles(df[f].iloc[:1000], buckets=10)
        save_baseline(baseline, baseline_file)
        print('Saved baseline to', baseline_file)
    else:
        baseline = load_baseline(baseline_file)

    # Compare recent window to baseline
    recent = df[features].iloc[-200:]

    psi_results = {}
    for f in features:
        # Build expected and actual Series from stored quantiles and recent values
        # Reconstruct expected series by using quantile edges as bins
        # For PSI calculation we will reuse calculate_psi by generating expected sample
        # Here we approximate expected by sampling uniformly between quantile bins
        quantiles = np.array(baseline[f])
        # If quantiles degenerate, skip
        if np.allclose(quantiles[0], quantiles[-1]):
            psi_results[f] = {'psi': 0.0, 'detail': 'degenerate_baseline'}
            continue

        # Create synthetic expected sample from quantile ranges
        expected_synth = []
        for i in range(len(quantiles)-1):
            a, b = quantiles[i], quantiles[i+1]
            expected_synth.extend(list(a + (b - a) * np.random.rand(100)))

        try:
            psi_val, details = calculate_psi(
                expected=pd.Series(expected_synth),
                actual=recent[f],
                buckets=10
            )
            psi_results[f] = {'psi': psi_val, 'detail': details}
        except Exception as e:
            psi_results[f] = {'psi': None, 'detail': f'error:{e}'}

    # Print summary
    # Build richer alert message
    print('PSI Summary:')
    msg_lines = []
    try:
        # Include model metadata if available
        meta_path = os.path.join(model_dir, 'metadata.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                meta = json.load(mf)
            msg_lines.append(f"Model: {meta.get('tag','unknown')} (source: {meta.get('source','unknown')})")
    except Exception:
        pass

    for f, res in psi_results.items():
        psi = res['psi'] if isinstance(res, dict) else res
        status = 'OK' if psi < 0.1 else ('WARN' if psi < 0.25 else 'ALERT')
        line = f" - {f}: PSI={psi:.4f} -> {status}"
        print(line)
        msg_lines.append(line)

    # Add link to report if exists
    report_path = 'backtest_results/report.md'
    if os.path.exists(report_path):
        msg_lines.append(f'Report: {os.path.abspath(report_path)}')

    # Save results
    out_path = os.path.join(model_dir, 'psi_check.json')
    with open(out_path, 'w') as fo:
        json.dump(psi_results, fo, default=str, indent=2)
    print('Wrote', out_path)
    # Exit non-zero if any ALERT (PSI >= 0.25)
    any_alert = any((isinstance(v, dict) and v.get('psi', 0) >= 0.25) for v in psi_results.values())
    if any_alert:
        print('PSI ALERT detected; sending alert and exiting with code 2')
        try:
                msg = "\n".join(msg_lines)
                send_telegram_alert(msg)
        except Exception:
            pass
        sys.exit(2)


if __name__ == '__main__':
    main()

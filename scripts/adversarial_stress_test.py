"""Adversarial stress test for PSI and model inference.

Usage:
  python scripts/adversarial_stress_test.py --model-dir MODELDIR --perturb shift --magnitude 0.5 --n 500

This script loads a model baseline (psi_baseline.json) if available, synthesizes
an in-distribution sample, applies a perturbation, and computes per-feature PSI
against the baseline using `monitoring.psi.calculate_psi`.
"""
import argparse
import json
import os
import numpy as np
import pandas as pd
from typing import Dict

try:
    from monitoring.psi import load_baseline, calculate_psi
except Exception:
    # Graceful fallback when run outside project path
    def load_baseline(path):
        with open(path, 'r') as f:
            return json.load(f)

    def calculate_psi(expected, actual, buckets=10):
        # minimal fallback: use simple distance metric
        e = np.asarray(expected).ravel()
        a = np.asarray(actual).ravel()
        return float(np.abs(np.nanmean(e) - np.nanmean(a))) , {"fallback": True}


def synthesize_from_quantiles(qs, n=500):
    q = np.array(qs)
    if q.size < 2 or np.allclose(q[0], q[-1]):
        return np.full(n, q[0] if q.size else 0.0)
    samples = []
    for i in range(len(q)-1):
        a, b = q[i], q[i+1]
        samples.append(np.random.uniform(a, b, size=max(1, n // (len(q)-1))))
    return np.concatenate(samples)[:n]


def apply_perturbation(arr: np.ndarray, mode: str, magnitude: float) -> np.ndarray:
    if mode == 'shift':
        return arr + magnitude
    if mode == 'scale':
        return arr * (1.0 + magnitude)
    if mode == 'spike':
        out = arr.copy()
        k = max(1, int(len(arr) * min(0.01, magnitude)))
        idx = np.random.choice(len(arr), k, replace=False)
        out[idx] = out[idx] * (1 + 10 * magnitude) + 1e6 * magnitude
        return out
    # default: no-op
    return arr


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', required=True)
    p.add_argument('--perturb', choices=['shift', 'scale', 'spike'], default='shift')
    p.add_argument('--magnitude', type=float, default=0.1)
    p.add_argument('--n', type=int, default=500)
    args = p.parse_args()

    baseline_path = os.path.join(args.model_dir, 'psi_baseline.json')
    if not os.path.exists(baseline_path):
        print(f"Baseline not found: {baseline_path}")
        return 2

    baseline = load_baseline(baseline_path)
    report: Dict[str, Dict] = {}

    for f, qs in baseline.items():
        if not qs:
            report[f] = {'error': 'no_quantiles'}
            continue

        exp = synthesize_from_quantiles(qs, n=args.n)
        actual = apply_perturbation(exp, args.perturb, args.magnitude)

        psi_val, details = calculate_psi(pd.Series(exp), pd.Series(actual))
        report[f] = {'psi': float(psi_val), 'details': details}

    out_path = os.path.join('backtest_results', f'adversarial_psi_{os.path.basename(args.model_dir)}.json')
    os.makedirs('backtest_results', exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"Wrote adversarial PSI report: {out_path}")
    # Print top offenders
    sorted_feats = sorted([(k, v.get('psi') or 0.0) for k, v in report.items()], key=lambda x: -x[1])[:10]
    print("Top features by PSI (sample):")
    for k, v in sorted_feats:
        print(f" - {k}: {v}")


if __name__ == '__main__':
    main()

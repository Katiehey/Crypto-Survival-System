"""Run adversarial perturbations using a specified baseline file.

Usage:
  python scripts/adversarial_with_baseline.py --baseline backtest_results/psi_rebaseline/psi_baseline_recomputed.json --perturb scale --magnitude 0.2 --n 500
"""
import argparse
import json
import numpy as np
import pandas as pd
from monitoring.psi import calculate_psi


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
    return arr


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline', required=True)
    p.add_argument('--perturb', choices=['shift','scale','spike'], default='scale')
    p.add_argument('--magnitude', type=float, default=0.2)
    p.add_argument('--n', type=int, default=500)
    args = p.parse_args()

    with open(args.baseline, 'r') as f:
        baseline = json.load(f)

    report = {}
    for f, qs in baseline.items():
        if not qs:
            report[f] = {'error': 'no_quantiles'}
            continue
        exp = synthesize_from_quantiles(qs, n=args.n)
        actual = apply_perturbation(exp, args.perturb, args.magnitude)
        psi_val, details = calculate_psi(pd.Series(exp), pd.Series(actual))
        report[f] = {'psi': float(psi_val), 'details': details}

    out = 'backtest_results/adversarial_with_baseline_report.json'
    with open(out, 'w') as fo:
        json.dump(report, fo, indent=2)
    top = sorted([(k,v['psi']) for k,v in report.items()], key=lambda x:-x[1])[:10]
    print('Wrote', out)
    print('Top features:')
    for k,v in top:
        print('-', k, v)

if __name__ == '__main__':
    main()

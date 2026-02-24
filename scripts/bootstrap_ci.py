"""
Bootstrap CI for mean total_pnl and max drawdown per mode
Reads `backtest_results/ml_vs_rule_walkforward.csv` and writes `backtest_results/bootstrap_ci.json`.
"""
import json
import numpy as np
import pandas as pd
import os


def bootstrap_ci(values, stat_func, n_boot=10000, ci=95):
    rng = np.random.default_rng(0)
    n = len(values)
    stats = []
    vals = np.array(values)
    for _ in range(n_boot):
        sample = rng.choice(vals, size=n, replace=True)
        stats.append(stat_func(sample))
    lo = np.percentile(stats, (100 - ci) / 2)
    hi = np.percentile(stats, 100 - (100 - ci) / 2)
    return float(np.mean(stats)), float(lo), float(hi)


def main():
    path = 'backtest_results/ml_vs_rule_walkforward.csv'
    if not os.path.exists(path):
        print('Missing', path)
        return

    df = pd.read_csv(path)

    results = {}
    for mode, g in df.groupby('mode'):
        pnls = g['total_pnl'].astype(float).values
        drawdowns = g['current_drawdown'].astype(float).values

        if len(pnls) == 0:
            continue

        mean_pnl, mean_lo, mean_hi = bootstrap_ci(pnls, np.mean, n_boot=10000, ci=95)

        # For max drawdown we compute sample max of drawdowns in each bootstrap resample
        def sample_max(x):
            return float(np.max(x))

        maxdd_mean, maxdd_lo, maxdd_hi = bootstrap_ci(drawdowns, sample_max, n_boot=10000, ci=95)

        results[mode] = {
            'n_folds': int(len(pnls)),
            'mean_pnl': mean_pnl,
            'mean_pnl_ci_95': [mean_lo, mean_hi],
            'max_drawdown_mean': maxdd_mean,
            'max_drawdown_ci_95': [maxdd_lo, maxdd_hi],
            'raw_pnls': pnls.tolist(),
            'raw_drawdowns': drawdowns.tolist()
        }

    out = 'backtest_results/bootstrap_ci.json'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)

    print('Wrote bootstrap CI to', out)


if __name__ == '__main__':
    main()

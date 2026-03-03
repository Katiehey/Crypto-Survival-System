"""Apply simple feature mitigations (winsorize/log) and recompute PSI.

Usage:
  python scripts/mitigate_and_recompute_psi.py --model-dir MODELDIR

This script loads `psi_baseline.json` from the model dir and attempts to
fetch recent data via the project's data provider. For numeric features it
computes PSI before and after applying mitigations (winsorize or log1p)
and writes `backtest_results/mitigated_psi_<model>.json`.
"""
import argparse
import json
import os
from typing import Dict

import numpy as np
import pandas as pd

from monitoring import psi as psi_mod


def winsorize_series(s: pd.Series, lower_pct=0.01, upper_pct=0.99) -> pd.Series:
    if s.dropna().empty:
        return s
    lo = np.nanpercentile(s.dropna(), 100 * lower_pct)
    hi = np.nanpercentile(s.dropna(), 100 * upper_pct)
    return s.clip(lo, hi)


def transform_actual(series: pd.Series, feature_name: str) -> pd.Series:
    # Apply log1p for volume-like and atr-like features
    low = feature_name.lower()
    out = series.copy()
    # Targeted transforms:
    # - For volume/atr: log1p + tighter winsorize
    # - For efficiency/regime_confidence: map to percentile if possible, else heavy winsorize
    if 'volume' in low or 'atr' in low:
        # For atr and volume, prefer percentile/rank mapping to stabilize distribution
        out = out.copy()
        try:
            # remove negatives for log and ranking
            cleaned = out.clip(lower=0)
            # map to percentile ranks
            ranks = cleaned.rank(pct=True) * 100.0
            # apply light log to raw magnitude if ranks are not informative
            if ranks.dropna().nunique() > 5:
                out = ranks
            else:
                out = np.log1p(cleaned)
                out = winsorize_series(out, 0.02, 0.98)
        except Exception:
            out = np.log1p(out.clip(lower=0))
            out = winsorize_series(out, 0.02, 0.98)
        # Additional targeted caps
        if 'atr_pct' in low or low == 'atr_pct':
            # tighten winsorization for ATR percent change features
            out = winsorize_series(out, 0.05, 0.95)
        if low == 'volume_ma' or low.endswith('_volume_ma'):
            # cap volume moving-average at 99th percentile to avoid outliers
            try:
                cap = np.nanpercentile(out.dropna(), 99)
                out = out.clip(upper=cap)
            except Exception:
                pass
    elif 'efficiency' in low or 'regime_confidence' in low:
        # For these engineered metrics, prefer percentile mapping if numeric rank is meaningful
        try:
            ranks = out.rank(pct=True) * 100.0
            out = ranks
        except Exception:
            out = winsorize_series(out, 0.01, 0.99)
    else:
        # Default mild winsorization
        out = winsorize_series(out, 0.01, 0.99)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', required=True)
    p.add_argument('--recent-window', type=int, default=200)
    args = p.parse_args()

    baseline_path = os.path.join(args.model_dir, 'psi_baseline.json')
    if not os.path.exists(baseline_path):
        print('Baseline missing:', baseline_path)
        return 2

    baseline = psi_mod.load_baseline(baseline_path)

    # Try to obtain recent_df
    recent_df = None
    try:
        from paper_trading.data_provider import create_data_provider
        prov = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
        recent_df = prov.get_historical_data(limit=max(1000, args.recent_window + 50))
    except Exception:
        recent_df = None

    results: Dict[str, Dict] = {}

    for f, quantiles in baseline.items():
        if not quantiles:
            results[f] = {'before': None, 'after': None, 'note': 'no_quantiles'}
            continue

        # Build synthetic expected
        q = np.array(quantiles)
        expected_synth = []
        for i in range(len(q)-1):
            a, b = q[i], q[i+1]
            expected_synth.extend(list(a + (b - a) * np.random.rand(100)))

        if recent_df is None or f not in recent_df.columns:
            results[f] = {'before': None, 'after': None, 'note': 'no_actual_data'}
            continue

        actual_series = recent_df[f].iloc[-args.recent_window:]
        # compute before
        psi_before, _ = psi_mod.calculate_psi(pd.Series(expected_synth), actual_series)

        # apply mitigation
        mitigated_actual = transform_actual(actual_series, f)
        psi_after, _ = psi_mod.calculate_psi(pd.Series(expected_synth), mitigated_actual)

        results[f] = {'before': float(psi_before) if psi_before is not None else None,
                      'after': float(psi_after) if psi_after is not None else None}

    out_path = os.path.join('backtest_results', f'mitigated_psi_{os.path.basename(args.model_dir)}.json')
    os.makedirs('backtest_results', exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)

    print('Wrote mitigation PSI report:', out_path)


if __name__ == '__main__':
    main()

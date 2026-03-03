import json
import os
import numpy as np
import pandas as pd
from typing import Tuple, Dict, List


def _get_bin_edges(expected: pd.Series, buckets: int = 10) -> np.ndarray:
    # Use expected distribution quantiles to form bins
    quantiles = np.linspace(0, 100, buckets + 1)
    edges = np.percentile(expected.dropna().values, quantiles)
    # Ensure monotonic increasing
    edges = np.unique(edges)
    if len(edges) <= 1:
        # fallback to tiny range
        v = expected.dropna().values
        if v.size == 0:
            return np.array([0.0, 1.0])
        return np.array([v.min(), v.max() + 1e-6])
    return edges


def calculate_psi(expected: pd.Series, actual: pd.Series, buckets: int = 10) -> Tuple[float, Dict]:
    """Calculate Population Stability Index (PSI) between two series.

    Returns (psi_value, details) where details contains per-bin contributions.
    """
    eps = 1e-6
    expected = expected.dropna()
    actual = actual.dropna()

    if expected.empty:
        return None, {"error": "empty_expected_series"}
    if actual.empty:
        return None, {"error": "empty_actual_series"}

    edges = _get_bin_edges(expected, buckets=buckets)

    expected_counts, _ = np.histogram(expected, bins=edges)
    actual_counts, _ = np.histogram(actual, bins=edges)

    # Apply simple Laplace smoothing to avoid empty-bin explosions
    # Add one pseudo-count to each bin for both expected and actual
    # This reduces sensitivity to single empty bins while preserving relative mass
    alpha = 1.0
    expected_counts = expected_counts.astype(float) + alpha
    actual_counts = actual_counts.astype(float) + alpha

    exp_sum = expected_counts.sum()
    act_sum = actual_counts.sum()

    if exp_sum == 0:
        return None, {"error": "empty_expected_counts", "expected_counts": expected_counts.tolist()}
    if act_sum == 0:
        return None, {"error": "empty_actual_counts", "actual_counts": actual_counts.tolist()}

    expected_pct = expected_counts / float(exp_sum)
    actual_pct = actual_counts / float(act_sum)

    # Compute per-bin PSI contributions
    contribs = (expected_pct - actual_pct) * np.log(expected_pct / actual_pct)
    psi_value = float(np.sum(contribs))

    details = {
        "edges": edges.tolist(),
        "expected_counts": expected_counts.tolist(),
        "actual_counts": actual_counts.tolist(),
        "expected_pct": expected_pct.tolist(),
        "actual_pct": actual_pct.tolist(),
        "contribs": contribs.tolist(),
        "psi": psi_value,
    }
    return psi_value, details


def compute_baseline_quantiles(series: pd.Series, buckets: int = 10) -> List[float]:
    quantiles = np.linspace(0, 100, buckets + 1)
    return np.percentile(series.dropna().values, quantiles).tolist()


def save_baseline(baseline: Dict, path: str) -> None:
    with open(path, 'w') as f:
        json.dump(baseline, f, indent=2)


def load_baseline(path: str) -> Dict:
    with open(path, 'r') as f:
        return json.load(f)


def run_model_psi_check(model_dir: str,
                        provider=None,
                        recent_window: int = 200,
                        buckets: int = 10,
                        warn_threshold: float = 0.1,
                        alert_threshold: float = 0.25) -> Dict:
    """Run PSI check for a production model directory.

    Returns a dict with per-feature PSI and overall status:
    { 'feature': {'psi': float, 'status': 'OK'|'WARN'|'ALERT'}, ... }
    """
    # Load baseline
    baseline_path = os.path.join(model_dir, 'psi_baseline.json')
    baseline = None
    if os.path.exists(baseline_path):
        baseline = load_baseline(baseline_path)

    # If provider not passed, attempt to create one lazily to obtain recent data
    recent_df = None
    if provider is None:
        try:
            from paper_trading.data_provider import create_data_provider
            provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
        except Exception:
            provider = None

    if provider is not None:
        df = provider.get_historical_data(limit=max(1000, recent_window + 50))
        # No need to validate features here; we'll compare only overlapping columns
        recent_df = df

    # If we don't have baseline but do have recent_df, create baseline
    if baseline is None and recent_df is not None:
        baseline = {}
        for col in recent_df.columns:
            # Skip non-numeric columns and obvious time/index fields to avoid
            # degenerate bin edges and empty histogram bins in PSI computations.
            lowname = col.lower()
            if (not np.issubdtype(recent_df[col].dtype, np.number)) or ('time' in lowname) or lowname in ('timestamp', 'index'):
                baseline[col] = []
                continue
            try:
                baseline[col] = compute_baseline_quantiles(recent_df[col].iloc[:1000], buckets=buckets)
            except Exception:
                baseline[col] = []
        save_baseline(baseline, baseline_path)

    results = {}
    overall_status = 'OK'

    if baseline is None or recent_df is None:
        return {'error': 'baseline_or_recent_missing', 'baseline_exists': os.path.exists(baseline_path)}

    # Use last `recent_window` rows as actual
    actual = recent_df.iloc[-recent_window:]

    for f, quantiles in baseline.items():
        # Skip timestamp/time-like features to avoid PSI explosions from epoch/binning
        lowf = f.lower()
        if 'time' in lowf or lowf in ('timestamp', 'index'):
            results[f] = {'psi': None, 'status': 'ignored_time'}
            continue
        if f not in actual.columns or not quantiles:
            results[f] = {'psi': None, 'status': 'missing'}
            continue

        # Build synthetic expected sample from quantiles
        q = np.array(quantiles)
        if np.allclose(q[0], q[-1]):
            psi_val = 0.0
        else:
            # Prefer smoothed/percentile variants to reduce PSI sensitivity for engineered features
            actual_series = actual[f]
            # Use percentile-smoothed variants where available (prefer percentile over raw smooth)
            if f == 'regime_confidence':
                if 'regime_confidence_smooth_percentile' in actual.columns:
                    actual_series = actual['regime_confidence_smooth_percentile']
                elif 'regime_confidence_percentile' in actual.columns:
                    actual_series = actual['regime_confidence_percentile']
                elif 'regime_confidence_smooth' in actual.columns:
                    actual_series = actual['regime_confidence_smooth']
            # volume percentiles: prefer smoothed percentile
            if f == 'volume_percentile' and 'volume_percentile_smooth' in actual.columns:
                actual_series = actual['volume_percentile_smooth']
            # efficiency ratio: prefer the smoothed variant if present
            if f == 'efficiency_ratio' and 'efficiency_ratio_smooth' in actual.columns:
                actual_series = actual['efficiency_ratio_smooth']

            expected_synth = []
            for i in range(len(q)-1):
                a, b = q[i], q[i+1]
                expected_synth.extend(list(a + (b - a) * np.random.rand(100)))
            psi_val, _ = calculate_psi(pd.Series(expected_synth), actual_series, buckets=buckets)

        status = 'OK'
        if psi_val >= alert_threshold:
            status = 'ALERT'
        elif psi_val >= warn_threshold:
            status = 'WARN'

        results[f] = {'psi': float(psi_val), 'status': status}

        if status == 'ALERT':
            overall_status = 'ALERT'
        elif status == 'WARN' and overall_status != 'ALERT':
            overall_status = 'WARN'

    return {'overall_status': overall_status, 'features': results}

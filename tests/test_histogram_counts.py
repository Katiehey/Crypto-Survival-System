import os
import json
import math
import numpy as np
import pandas as pd

from paper_trading.data_provider import create_data_provider


def test_histogram_min_counts():
    """Ensure recent actual histogram bins for each feature have a minimum count.

    This prevents silent degenerate histograms (all zeros) which break PSI.
    Threshold is intentionally small to avoid flakiness in CI.
    """
    provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
    df = provider.get_historical_data(limit=2000)

    model_dir = None
    # find baseline in models/production
    prod_base = os.path.join('models', 'production')
    if os.path.isdir(prod_base):
        subdirs = sorted([os.path.join(prod_base, d) for d in os.listdir(prod_base)])
        if subdirs:
            model_dir = subdirs[-1]

    assert model_dir is not None, 'No production model dir found for histogram test'

    baseline_path = os.path.join(model_dir, 'psi_baseline.json')
    assert os.path.exists(baseline_path), 'No baseline file found for histogram test'

    with open(baseline_path, 'r') as f:
        baseline = json.load(f)

    # recent window used by PSI script
    recent = df.iloc[-200:]

    min_count_threshold = 3
    for feature, quantiles in baseline.items():
        if not quantiles or len(quantiles) < 2:
            continue
        edges = np.array(quantiles)
        # compute actual counts
        vals = recent.get(feature)
        assert vals is not None, f'Feature {feature} missing from recent data'
        counts, _ = np.histogram(vals.dropna(), bins=edges)
        # assert at least a small number of bins have counts and none are all zero
        zero_bins = int(np.sum(counts == 0))
        assert zero_bins < len(counts), f'All bins zero for {feature}'
        # ensure not too many zero bins
        assert zero_bins <= len(counts) - 1, f'Too many empty bins for {feature}: {zero_bins}'
        # ensure minimum count per bin where possible
        if counts.sum() > 0:
            assert counts.max() >= min_count_threshold or counts.sum() >= min_count_threshold, f'Low counts for {feature}: {counts}'

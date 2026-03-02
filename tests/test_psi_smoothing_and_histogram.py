import os
import json
import numpy as np
import pandas as pd

from monitoring.psi import calculate_psi


def test_laplace_smoothing_prevents_infinite_psi():
    """A synthetic test: empty actual bin would previously cause extreme PSI; smoothing keeps it finite."""
    # Expected: distribution with one value repeated, creating potential empty bins
    expected = pd.Series(np.concatenate([np.linspace(0, 1, 100), np.linspace(1, 2, 100)]))
    # Actual: concentrated in a subset producing empty bins
    actual = pd.Series(np.concatenate([np.linspace(1.5, 2, 50)]))

    psi, details = calculate_psi(expected, actual, buckets=10)
    assert psi is not None
    assert np.isfinite(psi), 'PSI should be finite with smoothing applied'

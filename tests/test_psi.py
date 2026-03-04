import os
import json
import pandas as pd

from monitoring.psi import run_model_psi_check


def test_run_model_psi_check_creates_baseline(tmp_path):
    class Prov:
        def get_historical_data(self, limit=200):
            df = pd.DataFrame({
                'timestamp': pd.Series([1, 2, 3]),
                'atr': pd.Series([1.0, 2.0, 3.0]),
                'sym_str': pd.Series(['a', 'b', 'c'], dtype='string'),
            })
            return df

    model_dir = tmp_path / 'models' / 'production' / 'production_retrained'
    # ensure no baseline exists beforehand
    baseline_path = os.path.join(str(model_dir), 'psi_baseline.json')
    if os.path.exists(baseline_path):
        os.remove(baseline_path)

    res = run_model_psi_check(str(model_dir), provider=Prov(), recent_window=2)

    assert isinstance(res, dict)
    assert 'overall_status' in res
    # baseline file should be created
    assert os.path.exists(baseline_path)
    with open(baseline_path, 'r') as f:
        data = json.load(f)
    assert isinstance(data, dict)

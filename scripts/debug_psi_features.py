from paper_trading.data_provider import create_data_provider
from monitoring.psi import compute_baseline_quantiles, _get_bin_edges, calculate_psi
import numpy as np
import pandas as pd

provider = create_data_provider('historical', symbol='BTC/USDT', timeframe='1h')
df = provider.get_historical_data(limit=1200)
print('Loaded df shape:', df.shape)
features = ['atr_pct','atr_percentile','efficiency_ratio','efficiency_ratio_smooth','efficiency_percentile','volume_ratio','volume_percentile']
for f in features:
    if f not in df.columns:
        print(f, 'MISSING')
        continue
    s = df[f]
    print('\nFeature:', f)
    print('  count:', len(s), 'nan_count:', int(s.isna().sum()), 'min:', float(s.min()) if s.dropna().size>0 else None, 'max:', float(s.max()) if s.dropna().size>0 else None)
    try:
        q = compute_baseline_quantiles(s.iloc[:1000], buckets=10)
        print('  baseline quantiles:', q)
        # compute histogram using baseline edges
        # If baseline quantiles degenerate, print note
        if len(q) <= 1 or all(abs(q[i]-q[0]) < 1e-12 for i in range(len(q))):
            print('  degenerate baseline quantiles')
        else:
            edges = _get_bin_edges(pd.Series(q), buckets=10)
            print('  bin edges from baseline (len):', len(edges))
    except Exception as e:
        print('  baseline error', e)
    try:
        psi, details = calculate_psi(pd.Series(np.random.rand(100)), s.iloc[-200:], buckets=10)
        print('  sample psi vs recent:', psi)
        if isinstance(details, dict):
            print('  recent actual_counts:', details.get('actual_counts'))
    except Exception as e:
        print('  psi calc error', e)

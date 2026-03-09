#!/usr/bin/env python3
"""Generate simple histogram plots for top-N PSI features.

Produces PNGs into `backtest_results/psi_diagnostics/` for the top N features
by PSI value using the `detail` section in `psi_check.json`.
"""
import json
import os
import sys
import pathlib

project_root = pathlib.Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

OUT_DIR = 'backtest_results/psi_diagnostics'


def load_psi(path=None):
    if path and os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    # try to find latest model psi_check
    import glob
    candidates = glob.glob('models/production/*/psi_check.json')
    if candidates:
        with open(sorted(candidates)[-1], 'r') as f:
            return json.load(f)
    if os.path.exists('psi_check.json'):
        with open('psi_check.json', 'r') as f:
            return json.load(f)
    raise FileNotFoundError('psi_check.json not found')


def plot_hist(feature, detail, out_dir=OUT_DIR):
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return False

    edges = detail.get('edges')
    expected = detail.get('expected_pct')
    actual = detail.get('actual_pct')
    if not edges or not expected or not actual:
        return False

    os.makedirs(out_dir, exist_ok=True)
    x = range(len(expected))
    plt.figure(figsize=(6,3))
    plt.bar([i-0.2 for i in x], expected, width=0.4, label='expected')
    plt.bar([i+0.2 for i in x], actual, width=0.4, label='actual')
    plt.title(f'PSI bins: {feature}')
    plt.xlabel('bin')
    plt.ylabel('pct')
    plt.legend()
    out = os.path.join(out_dir, f'psi_{feature}.png')
    plt.tight_layout()
    plt.savefig(out)
    plt.close()
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    psi = load_psi(path)
    # collect numeric psi values
    vals = []
    for k, v in psi.items():
        if k.startswith('_'):
            continue
        try:
            pv = v.get('psi') if isinstance(v, dict) else v
            if pv is None:
                continue
            vals.append((k, float(pv), v.get('detail') if isinstance(v, dict) else None))
        except Exception:
            continue

    vals = sorted(vals, key=lambda x: -x[1])
    outputs = []
    for k, pv, detail in vals[:10]:
        if not detail:
            continue
        out = plot_hist(k, detail)
        outputs.append({'feature': k, 'psi': pv, 'plot': out})

    summary = {'generated': len(outputs), 'plots': outputs}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'triage_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)
    print('Wrote triage summary with', len(outputs), 'plots to', OUT_DIR)


if __name__ == '__main__':
    main()

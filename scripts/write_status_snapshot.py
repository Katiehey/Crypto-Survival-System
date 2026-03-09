#!/usr/bin/env python3
"""Write periodic PSI and risk snapshots to backtest_results/status and
produce a tiny HTML status page for quick inspection.

Usage:
  python scripts/write_status_snapshot.py --model-dir models/production/... --out-dir backtest_results/status

This is lightweight and has no external deps beyond the repo.
"""
import argparse
import json
import os
from datetime import datetime

import sys
import pathlib

# Ensure project root is on sys.path when running the script directly
project_root = pathlib.Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from monitoring.psi import run_model_psi_check


def write_snapshot(model_dir: str, out_dir: str = 'backtest_results/status'):
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    snapshot_path = os.path.join(out_dir, f'psi_snapshot_{ts}.json')

    try:
        res = run_model_psi_check(model_dir, recent_window=200, buckets=10)
        with open(snapshot_path, 'w') as f:
            json.dump({'timestamp': ts, 'result': res}, f, indent=2)
        print('Wrote', snapshot_path)
    except Exception as e:
        # Write a diagnostic file so CI artifacts capture the error
        err_path = os.path.join(out_dir, f'psi_snapshot_error_{ts}.json')
        try:
            import traceback
            with open(err_path, 'w') as ef:
                json.dump({'timestamp': ts, 'error': str(e), 'trace': traceback.format_exc()}, ef, indent=2)
            print('Wrote diagnostic', err_path)
        except Exception:
            print('Failed to write diagnostic file for snapshot error')

    # Update index.html with most recent snapshot links
    files = sorted([f for f in os.listdir(out_dir) if f.startswith('psi_snapshot_')])
    latest = files[-1] if files else None
    html_path = os.path.join(out_dir, 'index.html')
    try:
        with open(html_path, 'w') as hf:
            hf.write('<html><head><meta charset="utf-8"><title>PSI Status</title></head><body>')
            hf.write(f'<h1>PSI Status (generated {ts} UTC)</h1>')
            if latest:
                hf.write(f'<p>Latest snapshot: <a href="{latest}">{latest}</a></p>')
            hf.write('<h2>Recent snapshots</h2><ul>')
            for fn in files[-20:][::-1]:
                hf.write(f'<li><a href="{fn}">{fn}</a></li>')
            hf.write('</ul>')
            hf.write('</body></html>')
        print('HTML index:', html_path)
    except Exception as e:
        print('Failed to write HTML index:', e)

    print('Wrote', snapshot_path)
    print('HTML index:', html_path)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', required=True)
    p.add_argument('--out-dir', default='backtest_results/status')
    args = p.parse_args()
    write_snapshot(args.model_dir, args.out_dir)

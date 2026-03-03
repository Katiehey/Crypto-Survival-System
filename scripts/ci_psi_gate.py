#!/usr/bin/env python3
"""CI PSI gate script.

Runs `monitoring.psi.run_model_psi_check` for a model dir, writes report
to `backtest_results/ci_psi_report.json` and exits non-zero if overall_status
is 'ALERT'.
"""
import argparse
import json
import os
import sys

from monitoring import psi as psi_mod


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', required=True)
    p.add_argument('--recent-window', type=int, default=200)
    p.add_argument('--buckets', type=int, default=10)
    args = p.parse_args()

    report = psi_mod.run_model_psi_check(
        model_dir=args.model_dir,
        recent_window=args.recent_window,
        buckets=args.buckets,
        warn_threshold=0.1,
        alert_threshold=0.25,
    )

    os.makedirs('backtest_results', exist_ok=True)
    out = 'backtest_results/ci_psi_report.json'
    with open(out, 'w') as f:
        json.dump(report, f, indent=2)

    overall = report.get('overall_status')
    print(f"CI PSI overall_status={overall}")
    if overall == 'ALERT':
        print('PSI ALERT - failing CI gate')
        sys.exit(2)
    # warn is non-fatal but printed
    if overall == 'WARN':
        print('PSI WARN - continue but review')
    sys.exit(0)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Copy promoted baseline into a model directory.

Usage:
  python scripts/promote_baseline_to_model.py --model-name production_retrained_winsor_quantile_long

This script copies `ops/promoted_baselines/<model>/psi_baseline.json` into
`models/production/<model>/psi_baseline.json` (creates destination dir if needed).
"""
import argparse
import os
import shutil


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-name', required=True)
    args = p.parse_args()

    src = os.path.join('ops', 'promoted_baselines', args.model_name, 'psi_baseline.json')
    dst_dir = os.path.join('models', 'production', args.model_name)
    dst = os.path.join(dst_dir, 'psi_baseline.json')

    if not os.path.exists(src):
        print('Promoted baseline not found:', src)
        return 2
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src, dst)
    print('Copied', src, '->', dst)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

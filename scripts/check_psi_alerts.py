#!/usr/bin/env python3
"""Check `psi_check.json` for ALERTs on non-whitelisted features.

Exits 0 when OK, 2 when ALERTs found, 1 on error.
"""
import json
import os
import sys
import pathlib

project_root = pathlib.Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def find_latest_model(base_dir='models/production'):
    import glob
    dirs = sorted(glob.glob(os.path.join(base_dir, '*')))
    if not dirs:
        return None
    return dirs[-1]


def load_exceptions():
    path = os.path.join('ops', 'psi_exceptions.json')
    if not os.path.exists(path):
        return set()
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return set(data if isinstance(data, list) else [])
    except Exception:
        return set()


def main():
    model_dir = None
    if len(sys.argv) > 1 and sys.argv[1].startswith('--'):
        # allow --model-dir foo
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument('--model-dir', default=None)
        p.add_argument('--path', default=None)
        args = p.parse_args()
        model_dir = args.model_dir
    # fallback
    if model_dir is None:
        model_dir = find_latest_model()

    psi_path = None
    if model_dir and os.path.isdir(model_dir):
        candidate = os.path.join(model_dir, 'psi_check.json')
        if os.path.exists(candidate):
            psi_path = candidate
    if not psi_path and os.path.exists('psi_check.json'):
        psi_path = 'psi_check.json'
    if not psi_path:
        print('No psi_check.json found')
        return 1

    try:
        with open(psi_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print('Failed to load', psi_path, e)
        return 1

    exceptions = load_exceptions()
    alert_threshold = 0.25
    alerts = []
    for k, v in data.items():
        if k.startswith('_'):
            continue
        if k in exceptions:
            continue
        try:
            psi_val = None
            if isinstance(v, dict):
                psi_val = v.get('psi')
            else:
                psi_val = v
            if psi_val is None:
                continue
            if float(psi_val) >= alert_threshold:
                alerts.append((k, float(psi_val)))
        except Exception:
            continue

    if alerts:
        print('PSI ALERTS detected for non-whitelisted features:')
        for f, val in sorted(alerts, key=lambda x: -x[1]):
            print(f' - {f}: {val}')
        return 2

    print('No PSI ALERTS for non-whitelisted features')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Reserialize model pickles in `models/production/*` using current sklearn/joblib.

This makes a backup of the original `model.pkl` as `model.pkl.bak` and writes
a fresh `model.pkl` serialized by `joblib.dump` using the currently installed
scikit-learn/joblib versions to avoid InconsistentVersionWarning on load.
"""
import os
from glob import glob
import shutil
import json

def reserialize_model(model_path):
    try:
        import joblib
    except Exception as e:
        print('joblib not available:', e)
        return False

    if not os.path.exists(model_path):
        print('model not found:', model_path)
        return False

    bak_path = model_path + '.bak'
    try:
        # Backup original
        if not os.path.exists(bak_path):
            shutil.copy2(model_path, bak_path)
            print('Backed up', model_path, '->', bak_path)
        # Load and immediately re-dump with joblib
        m = joblib.load(model_path)
        joblib.dump(m, model_path)
        print('Reserialized', model_path)
        return True
    except Exception as e:
        print('Failed to reserialize', model_path, '-', e)
        return False


def main(base_dir='models/production'):
    dirs = sorted(glob(os.path.join(base_dir, '*')))
    if not dirs:
        print('No production model dirs found under', base_dir)
        return

    for d in dirs:
        model_path = os.path.join(d, 'model.pkl')
        meta_path = os.path.join(d, 'metadata.json')
        ok = reserialize_model(model_path)
        if ok:
            # annotate metadata
            try:
                if os.path.exists(meta_path):
                    with open(meta_path, 'r') as mf:
                        meta = json.load(mf)
                else:
                    meta = {}
                meta['reserialized_with'] = "reserialize_models.py"
                import datetime
                meta['reserialized_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
                with open(meta_path, 'w') as mf:
                    json.dump(meta, mf, indent=2)
                print('Updated metadata for', d)
            except Exception as e:
                print('Failed to update metadata for', d, e)


if __name__ == '__main__':
    main()

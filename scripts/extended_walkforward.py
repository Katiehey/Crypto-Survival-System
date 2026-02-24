"""
Run extended walk-forward ML vs rule comparison with more folds/windows.
Uses the specified model (default: best candidate) and writes to
`backtest_results/ml_vs_rule_walkforward.csv`.
"""
from scripts.backtest_ml_vs_rule import run_walkforward
import argparse

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model', type=str, default='models/walkforward/20260214_230629_fold2/model.pkl')
    p.add_argument('--folds', type=int, default=8)
    p.add_argument('--window', type=int, default=250)
    p.add_argument('--step', type=int, default=125)
    args = p.parse_args()

    print(f'Running extended walk-forward: folds={args.folds}, window={args.window}, step={args.step}, model={args.model}')
    run_walkforward(folds=args.folds, window=args.window, step=args.step, model_path=args.model)

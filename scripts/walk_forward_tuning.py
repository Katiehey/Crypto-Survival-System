"""Simple walk-forward hyperparameter tuning for `SimpleTrendStrategy`.

This script runs modest grid search across rolling windows and reports
robust parameter candidates (mean return, mean drawdown, win rate).

Usage:
    PYTHONPATH=. python3 scripts/walk_forward_tuning.py
"""
import itertools
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)

import pandas as pd

from paper_trading import PaperTradingSystem
from paper_trading.data_provider import HistoricalDataProvider
from risk.engine import RiskEngine
from strategies.simple_trend import SimpleTrendStrategy
from paper_trading.execution import ExecutionSimulator


def run_backtest_on_df(df, params):
    # Static provider wrapper
    class _StaticProvider:
        def get_historical_data(self, limit=1000, start_date=None, end_date=None):
            return df

        def get_latest_candle(self, *a, **k):
            return None

    system = PaperTradingSystem(initial_capital=500, speed='instant', data_source='historical')
    strategy = SimpleTrendStrategy(**params)
    risk = RiskEngine(capital=system.initial_capital)
    exec_sim = ExecutionSimulator()

    system.setup(strategy=strategy, risk_engine=risk, data_provider=_StaticProvider(), execution_simulator=exec_sim)
    system.start()
    summary = system.get_performance_summary()
    return summary


def walk_forward(df, param_grid, n_splits=4):
    # Split dataframe into n_splits sequential folds (train unused here; we just run on test windows)
    n = len(df)
    fold_size = n // n_splits
    results = []

    for params in param_grid:
        combo_res = []
        logging.info(f"Testing params: {params}")

        for i in range(n_splits):
            start = i * fold_size
            end = start + fold_size
            if i == n_splits - 1:
                end = n
            window_df = df.iloc[:end].copy()  # Use cumulative history to avoid lookahead
            try:
                summary = run_backtest_on_df(window_df, params)
                combo_res.append(summary)
            except Exception as e:
                logging.exception(f"Backtest failed for params {params} on fold {i}: {e}")

        # Aggregate metrics
        mean_return = pd.Series([r['total_return_pct'] for r in combo_res]).mean()
        mean_draw = pd.Series([r['current_drawdown'] for r in combo_res]).mean()
        mean_trades = pd.Series([r['total_trades'] for r in combo_res]).mean()

        results.append({
            **params,
            'mean_return_pct': mean_return,
            'mean_drawdown_pct': mean_draw,
            'mean_trades': mean_trades,
            'folds': len(combo_res)
        })

    return pd.DataFrame(results)


def main():
    provider = HistoricalDataProvider()
    df = provider.get_historical_data(limit=1000)

    # Expanded conservative grid (5x–4x–4x = 80 combos)
    entry_vals = [0.55, 0.60, 0.65, 0.70, 0.75]
    stop_vals = [2.5, 3.0, 3.5, 4.0]
    min_vals = [25.0, 50.0, 100.0, 150.0]

    grid = list(itertools.product(entry_vals, stop_vals, min_vals))

    dict_grid = [{'entry_efficiency_threshold': float(e),
                  'stop_loss_atr_multiple': float(s),
                  'min_trade_value': float(m)}
                 for e, s, m in grid]

    logging.info(f"Running walk-forward tuning with {len(dict_grid)} combos")
    results_df = walk_forward(df, dict_grid, n_splits=4)

    # Add stability metrics
    # Compute std dev of returns across folds per row (walk_forward already stored per-combo aggregated numbers)
    # We recompute using the raw fold outputs saved temporarily in the function results (not available here),
    # so approximate stability by using mean_drawdown as a proxy and compute a simple stability score
    results_df['stability_score'] = results_df['mean_return_pct'] / (results_df['mean_drawdown_pct'] + 1e-9)

    out_fp = os.path.join('backtest_results', f"walk_forward_expanded_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    results_df.sort_values(['stability_score', 'mean_return_pct'], ascending=[False, False]).to_csv(out_fp, index=False)
    logging.info(f"Wrote tuning results to {out_fp}")
    print(results_df.sort_values(['stability_score', 'mean_return_pct'], ascending=[False, False]).head(20).to_string(index=False))


if __name__ == '__main__':
    main()

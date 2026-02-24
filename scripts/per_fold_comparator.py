"""
Run each walk-forward model individually across the same folds and
save detailed per-fold trades, equity history, and a summary.

Outputs go to `backtest_results/walkforward_per_model/<model_tag>/fold<i>_*`.
"""
import os
import sqlite3
import argparse
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt

from config.system_config import SYSTEM_CONFIG
from strategies.orchestrator import MultiRegimeOrchestrator
from paper_trading import PaperTradingSystem
from paper_trading.data_provider import HistoricalDataProvider
from paper_trading.execution import ExecutionSimulator
from risk.engine import RiskEngine


def load_candles_from_db(db_path: str, limit: int = None) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM candles
        ORDER BY timestamp DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


class StaticHistoricalProvider(HistoricalDataProvider):
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(**kwargs)
        self._static_df = df.copy().reset_index(drop=True)

    def get_historical_data(self, limit: int = 1000, start_date=None, end_date=None):
        return self._static_df.copy()


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def run_model_on_folds(model_dir: str, out_base: str, folds: int = 3, window: int = 500, step: int = 250):
    model_path = os.path.join(model_dir, 'model.pkl')
    model_tag = os.path.basename(model_dir.rstrip('/'))
    out_dir = os.path.join(out_base, model_tag)
    ensure_dir(out_dir)

    df = load_candles_from_db(SYSTEM_CONFIG.DB_PATH, limit=2000)

    for i in range(folds):
        start = i * step
        end = start + window
        if end > len(df):
            break
        df_slice = df.iloc[start:end].reset_index(drop=True)

        try:
            from regime.features import calculate_complete_pipeline
            df_proc = calculate_complete_pipeline(df_slice)
        except Exception:
            df_proc = df_slice.copy()

        orchestrator = MultiRegimeOrchestrator(use_ml=True, ml_model_path=model_path)

        data_provider = StaticHistoricalProvider(df_proc,
                                                 db_path=SYSTEM_CONFIG.DB_PATH,
                                                 symbol=SYSTEM_CONFIG.TRADING_PAIR,
                                                 timeframe=SYSTEM_CONFIG.PRIMARY_TIMEFRAME)
        risk_engine = RiskEngine(capital=float(SYSTEM_CONFIG.STARTING_CAPITAL))
        exec_sim = ExecutionSimulator()

        pts = PaperTradingSystem(
            initial_capital=float(SYSTEM_CONFIG.STARTING_CAPITAL),
            symbol=SYSTEM_CONFIG.TRADING_PAIR,
            timeframe=SYSTEM_CONFIG.PRIMARY_TIMEFRAME,
            speed='instant',
            data_source='historical'
        )

        pts.setup(strategy=orchestrator, risk_engine=risk_engine, data_provider=data_provider, execution_simulator=exec_sim)
        pts.start()

        # Save per-trade CSV
        trades_df = pd.DataFrame(pts.closed_trades)
        trades_out = os.path.join(out_dir, f'fold{i}_trades.csv')
        if not trades_df.empty:
            trades_df.to_csv(trades_out, index=False)
        else:
            # write empty with columns
            trades_df.to_csv(trades_out, index=False)

        # Save equity history
        eq_df = pd.DataFrame(pts.equity_history)
        eq_out = os.path.join(out_dir, f'fold{i}_equity.csv')
        eq_df.to_csv(eq_out, index=False)

        # Save summary
        summary = pts.get_performance_summary()
        import json
        summary_out = os.path.join(out_dir, f'fold{i}_summary.json')
        with open(summary_out, 'w') as f:
            json.dump(summary, f, default=str, indent=2)

        # Plot equity curve
        fig_out = os.path.join(out_dir, f'fold{i}_equity.png')
        try:
            plt.figure(figsize=(8,4))
            if 'timestamp' in eq_df.columns:
                x = pd.to_datetime(eq_df['timestamp'])
            else:
                x = range(len(eq_df))
            plt.plot(x, eq_df['capital'], label='equity')
            plt.title(f'{model_tag} - fold {i} equity')
            plt.xlabel('time')
            plt.ylabel('capital')
            plt.grid(True)
            plt.legend()
            plt.tight_layout()
            plt.savefig(fig_out)
            plt.close()
        except Exception:
            # plotting optional
            pass

        print(f"Saved fold {i} outputs to {out_dir}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--models-dir', type=str, default='models/walkforward')
    p.add_argument('--out-dir', type=str, default='backtest_results/walkforward_per_model')
    p.add_argument('--folds', type=int, default=3)
    p.add_argument('--window', type=int, default=500)
    p.add_argument('--step', type=int, default=250)
    args = p.parse_args()

    ensure_dir(args.out_dir)

    # Discover model folders
    model_dirs = []
    if os.path.exists(args.models_dir):
        for name in sorted(os.listdir(args.models_dir)):
            full = os.path.join(args.models_dir, name)
            if os.path.isdir(full) and os.path.exists(os.path.join(full, 'model.pkl')):
                model_dirs.append(full)

    if not model_dirs:
        print('No walkforward models found in', args.models_dir)
        return

    for m in model_dirs:
        run_model_on_folds(m, args.out_dir, folds=args.folds, window=args.window, step=args.step)


if __name__ == '__main__':
    main()

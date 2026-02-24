"""
Run a quick backtest comparing ML-augmented orchestrator vs baseline orchestrator.
This is a smoke comparator using the small model at `models/smoke/model.pkl`.
"""
import argparse
import pandas as pd
import os
import sqlite3

from config.system_config import SYSTEM_CONFIG
from strategies.orchestrator import MultiRegimeOrchestrator
from paper_trading import PaperTradingSystem
from paper_trading.data_provider import HistoricalDataProvider
from paper_trading.execution import ExecutionSimulator
from risk.engine import RiskEngine
from paper_trading.data_provider import HistoricalDataProvider


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


def run_smoke(use_ml: bool, model_path: str = None):
    # small smoke: load 500 candles and run paper trading loop
    df = load_candles_from_db(SYSTEM_CONFIG.DB_PATH, limit=500)

    # Create orchestrator with or without ML
    orchestrator = MultiRegimeOrchestrator(use_ml=use_ml, ml_model_path=model_path)

    # Create system components
    data_provider = HistoricalDataProvider(db_path=SYSTEM_CONFIG.DB_PATH, symbol=SYSTEM_CONFIG.TRADING_PAIR, timeframe=SYSTEM_CONFIG.PRIMARY_TIMEFRAME)
    risk_engine = RiskEngine(capital=float(SYSTEM_CONFIG.STARTING_CAPITAL))
    exec_sim = ExecutionSimulator()

    # Create and setup paper trading system
    pts = PaperTradingSystem(
        initial_capital=float(SYSTEM_CONFIG.STARTING_CAPITAL),
        symbol=SYSTEM_CONFIG.TRADING_PAIR,
        timeframe=SYSTEM_CONFIG.PRIMARY_TIMEFRAME,
        speed='instant',
        data_source='historical'
    )

    pts.setup(strategy=orchestrator, risk_engine=risk_engine, data_provider=data_provider, execution_simulator=exec_sim)

    # Run historical simulation (start will call internal _run_historical_simulation)
    pts.start()

    # Collect summary
    summary = pts.get_performance_summary()

    out = 'backtest_results/ml_vs_rule_smoke_{mode}.json'.format(mode='ml' if use_ml else 'rule')
    os.makedirs('backtest_results', exist_ok=True)
    import json
    with open(out, 'w') as f:
        json.dump(summary, f, default=str, indent=2)

    print(f"Wrote results to {out}")


class StaticHistoricalProvider(HistoricalDataProvider):
    """
    A small data provider that returns a preloaded DataFrame for deterministic folds.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(**kwargs)
        self._static_df = df.copy().reset_index(drop=True)

    def get_historical_data(self, limit: int = 1000, start_date=None, end_date=None):
        # Return the static DataFrame regardless of limit to force deterministic fold
        return self._static_df.copy()


def run_fold(df_slice: pd.DataFrame, use_ml: bool, model_path: str = None):
    # Ensure features and regime classification present for the slice
    try:
        from regime.features import calculate_complete_pipeline
        df_proc = calculate_complete_pipeline(df_slice)
    except Exception:
        # If pipeline fails, fall back to the raw slice but warn downstream
        df_proc = df_slice.copy()

    orchestrator = MultiRegimeOrchestrator(use_ml=use_ml, ml_model_path=model_path)

    data_provider = StaticHistoricalProvider(df_proc, db_path=SYSTEM_CONFIG.DB_PATH,
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
    return pts.get_performance_summary()


def run_walkforward(folds: int = 3, window: int = 500, step: int = 250, model_path: str = None):
    # Load a larger set of candles and create overlapping windows
    df = load_candles_from_db(SYSTEM_CONFIG.DB_PATH, limit=2000)
    rows = []
    for i in range(folds):
        start = i * step
        end = start + window
        if end > len(df):
            break
        df_slice = df.iloc[start:end].reset_index(drop=True)

        for mode in ['rule', 'ml']:
            use_ml = (mode == 'ml')
            summary = run_fold(df_slice, use_ml=use_ml, model_path=model_path if use_ml else None)
            summary_row = {'fold': i, 'mode': mode}
            summary_row.update(summary)
            rows.append(summary_row)

    out_csv = 'backtest_results/ml_vs_rule_walkforward.csv'
    os.makedirs('backtest_results', exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f'Wrote walk-forward summary to {out_csv}')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model', type=str, default='models/smoke/model.pkl')
    args = p.parse_args()

    print('Running 3-fold walk-forward ML vs rule comparison...')
    run_walkforward(folds=3, window=500, step=250, model_path=args.model)

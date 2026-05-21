"""
optimize.py — Optuna hyperparameter optimizer.

Finds the best strategy parameters by running the walk-forward backtest
as the objective function across hundreds of parameter combinations.
Parameters are tested against 400 days of real BTC/USDT 1h history.

Usage:
    python optimize.py                        # 100 trials, maximize Sharpe
    python optimize.py --trials 200           # more trials = better search
    python optimize.py --metric profit_factor # alternative objective
    python optimize.py --metric win_rate

Results are saved to ops/best_params.json.
Copy the printed .env lines to your .env to activate the best params.
"""

import argparse
import json
import logging
from pathlib import Path

import config  # import first so we can override its module-level attributes

logging.basicConfig(
    level=logging.WARNING,   # suppress per-fold backtest noise during search
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("optimize")

BEST_PARAMS_PATH = Path("ops/best_params.json")


def run_optimization(n_trials: int = 100, metric: str = "sharpe", days: int = 730):
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        print("Optuna not installed. Run: pip install optuna")
        return None

    from backtest import WalkForwardBacktester

    print(f"Fetching {days} days of historical data (this may take ~90s)...")
    bt = WalkForwardBacktester()
    df    = bt.fetch_historical(days=days, timeframe="1h")
    df_4h = bt.fetch_historical(days=days, timeframe="4h")
    print(f"Fetched {len(df)} 1h candles, {len(df_4h)} 4h candles. Starting {n_trials}-trial search...\n")

    def objective(trial: "optuna.Trial") -> float:  # type: ignore[name-defined]
        # ── Override config module attributes for this trial ──────────────────
        # (Python modules are singletons — all code in the same process sees this)
        config.RSI_TREND_BUY_MIN   = trial.suggest_float("rsi_trend_buy_min",  50.0, 65.0)
        config.RSI_RANGE_BUY_MAX   = trial.suggest_float("rsi_range_buy_max",  22.0, 38.0)
        config.ADX_TREND_THRESHOLD = trial.suggest_float("adx_threshold",      18.0, 35.0)
        config.ATR_STOP_MULT       = trial.suggest_float("atr_stop_mult",       1.0,  2.5)
        config.ATR_TARGET_MULT     = trial.suggest_float("atr_target_mult",     1.5,  4.5)
        config.VOLUME_SPIKE_MIN    = trial.suggest_float("volume_spike_min",    1.0,  3.0)

        # Re-instantiate classes that read config at construction time
        from agents import TechnicalAgent
        from strategy import RegimeDetector, TradingStrategy
        bt.technical  = TechnicalAgent()
        bt.regime_det = RegimeDetector()
        bt.strategy   = TradingStrategy()

        result = bt.run(df, df_4h=df_4h)

        # Require at least 20 trades — fewer means the optimizer is cherry-picking
        # a handful of lucky trades, which inflates Sharpe artificially
        if result.total_trades < 20:
            return -10.0

        if metric == "sharpe":
            return result.sharpe_ratio
        elif metric == "profit_factor":
            return min(result.profit_factor, 5.0)   # cap to avoid outlier dominance
        elif metric == "win_rate":
            return result.win_rate_pct
        return result.sharpe_ratio

    study = optuna.create_study(direction="maximize")
    # WARNING: do not pass n_jobs > 1 here — the objective mutates config module
    # attributes (shared singleton), which causes data races under parallelism.
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    best   = study.best_params
    best_v = study.best_value
    sep    = "─" * 58

    print(f"\n{sep}")
    print(f"  OPTIMIZATION COMPLETE")
    print(f"  Best {metric}: {best_v:.4f}  |  Trials: {n_trials}")
    print(sep)
    print()
    print("  .env lines to copy  (paste into your .env file to activate):")
    print()
    env_lines = [
        f"RSI_TREND_BUY_MIN={best['rsi_trend_buy_min']:.1f}",
        f"RSI_RANGE_BUY_MAX={best['rsi_range_buy_max']:.1f}",
        f"ADX_TREND_THRESHOLD={best['adx_threshold']:.1f}",
        f"ATR_STOP_MULT={best['atr_stop_mult']:.2f}",
        f"ATR_TARGET_MULT={best['atr_target_mult']:.2f}",
        f"VOLUME_SPIKE_MIN={best['volume_spike_min']:.2f}",
    ]
    for line in env_lines:
        print(f"  {line}")
    print()
    print(f"  Saved full results → {BEST_PARAMS_PATH}")
    print(f"{sep}\n")

    output = {
        "metric":     metric,
        "best_value": round(best_v, 4),
        "n_trials":   n_trials,
        "params":     {k: round(v, 4) for k, v in best.items()},
        "env_lines":  env_lines,
    }
    BEST_PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BEST_PARAMS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    return output


def main():
    parser = argparse.ArgumentParser(description="Strategy hyperparameter optimizer")
    parser.add_argument(
        "--trials", type=int, default=100,
        help="Number of Optuna trials (default: 100, more = better search)",
    )
    parser.add_argument(
        "--metric", choices=["sharpe", "profit_factor", "win_rate"],
        default="sharpe",
        help="Objective to maximise (default: sharpe)",
    )
    parser.add_argument(
        "--days", type=int, default=730,
        help="Days of historical data to fetch (default: 730 = ~2 years)",
    )
    args = parser.parse_args()
    run_optimization(args.trials, args.metric, args.days)


if __name__ == "__main__":
    main()

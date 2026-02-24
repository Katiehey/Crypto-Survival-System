# ML Integration — Design & Runbook

Purpose
- Prototype a low-risk ML signal to augment rule-based strategies.
- Keep ML optional and always gated by existing risk controls.

Goals
- Predict short-term price movement (next candle return sign) or probability of positive return.
- Provide a confidence score to combine with rule signals.
- Ensure model choices are validated by walk‑forward CV and prefer stability over peak returns.

Data sources
- Historical candles stored in `data/trading.db` accessed via `DataFetcher`.
- Feature generation uses existing code in `regime/features.py` (ATR, Efficiency Ratio, volume metrics, regime labels).

Feature set (initial)
- `close`, `atr`, `atr_pct`, `atr_percentile`
- `efficiency_ratio`, `efficiency_ratio_smooth`, `efficiency_percentile`
- `volume`, `volume_ma`, `volume_ratio`, `volume_percentile`, `volume_spike`
- `regime`, `regime_confidence`, `regime_tradable`
- Lagged returns: `ret_1`, `ret_3`, `ret_6`

Labeling
- Binary label: `target_up = (future_return_1 > 0)` — simple, low-overfit target for short-term signal.
- Option: regression predicting `future_return_1` for sizing.

Model choices (prototype)
- Lightweight classifiers: `sklearn.ensemble.RandomForestClassifier` or `lightgbm` (if available).
- Use scikit-learn first (widespread, easy CI). Add LightGBM as an option later.

Validation
- Walk‑forward CV using existing folds from `scripts/walk_forward_tuning.py`.
- Metrics: fold mean return_pct (backtest), AUC (classification), precision@k, and a stability score (mean_return / mean_drawdown).

Safety & Fallbacks
- ML is optional toggle in `strategies/orchestrator.py`.
- ML-only trades are *never* allowed to bypass `risk.engine`.
- Default: ML augments rule signal; if ML confidence < threshold or model unavailable, fall back to pure rule-based decision.

Artefacts & Versioning
- Save model to `models/<timestamp>_<gitsha>/model.pkl` with `metadata.json` (params, metrics, training date, git sha).

Monitoring & Drift
- Periodic PSI and feature distribution checks in `monitoring/model_monitor.py`.
- Performance monitoring (P&L, hit rate) and alerting integrated with `paper_trading/monitor.py`.

Rollout Plan
1. Prototype (offline): `scripts/ml_features.py` + `scripts/train_model.py` → produce model artefact.
2. Backtest comparison: `scripts/backtest_ml_vs_rule.py` across walk‑forward folds.
3. Canary: enable ML on a small fraction of signals (config flag) in paper trading mode.
4. Full rollout: enable ML as primary signal only after stability confirmed across folds.

Runbook (quick)
- Extract features (sample 500 candles):

```bash
PYTHONPATH=. python3 scripts/ml_features.py --limit 500 --out data/processed/features_sample.csv
```

- Train small model (smoke):

```bash
PYTHONPATH=. python3 scripts/train_model.py --features data/processed/features_sample.csv --out models/smoke/
```

- Backtest ML vs rule (after training):

```bash
PYTHONPATH=. python3 scripts/backtest_ml_vs_rule.py --model models/smoke/model.pkl
```

Notes
- Keep ML experiments isolated under `models/` and add model checks to CI.
- Start simple, prefer explainable features, and always trust the `risk.engine` guardrails.

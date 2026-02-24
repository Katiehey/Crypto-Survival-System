## Monitoring and PSI Runbook

This document explains runtime and CI monitoring for the production ML model.

- PSI thresholds:
  - OK: PSI < 0.10
  - WARN: 0.10 <= PSI < 0.25
  - ALERT: PSI >= 0.25 (CI will fail and runtime gating blocks model load)
- CI behavior: `scripts/run_psi_check.py` is invoked by `ci_smoke.yml`. If any feature returns ALERT, the CI step exits non-zero and a Telegram alert is sent.
- Runtime gating: `paper_trading.ml_inference.MLInference` runs a PSI check when loading the production model and raises `RuntimeError` if PSI is ALERT.

Remediation steps on ALERT:
1. Review `models/production/*/psi_check.json` and `psi_baseline.json`.
2. Recompute baseline from a larger historical sample if appropriate, using `scripts/run_psi_check.py` with a stable dataset.
3. If drift is confirmed, consider retraining / roll-forwarding the model and re-running the production smoke.

Secrets: CI requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in repository Secrets.

Contact: ops@yourorg.example

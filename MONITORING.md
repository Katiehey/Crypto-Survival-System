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


Kill-switch and emergency runbook
--------------------------------

- File-based kill switch: create a file named `STOP_TRADING` in the repository root to immediately abort any running historical paper-trading run. The system checks for this file at each candle and will stop gracefully.
- Emergency steps:
  1. Create `STOP_TRADING` in repo root (`touch STOP_TRADING`) to stop runs.
  2. If running on a remote host, SSH in and stop the process (e.g., `pkill -f run_production_smoke.py`) and create `STOP_TRADING` as a safety latch.
  3. Deactivate ML gating (for investigation) by removing or replacing the production model, but only after triage.
  4. For urgent shutdowns, revoke exchange API keys used for the paper environment.

Post-deploy checklist before enabling live paper trading
-----------------------------------------------------

- Run `scripts/dry_run_paper_trading.py --limit 500 --speed instant` and confirm no exceptions and reasonable trade counts.
- Run `scripts/run_psi_check.py` and ensure PSI is OK or WARN (no ALERT).
- Validate `risk/engine.py` limits are conservative for R500: check `RISK_LIMITS` in `config/system_config.py`.
- Ensure CI secrets and monitoring alerts are configured and verified.


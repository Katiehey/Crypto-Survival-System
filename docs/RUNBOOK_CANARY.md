**Canary Runbook**

- **Purpose**: Safely run a small-scale live paper trading canary to validate model and pipeline changes.

- **Pre-checks**:
  - Ensure `ops/psi_exceptions.json` and `ops/kill_switch.json` exist and values reviewed.
  - Verify CI adversarial PSI report is green or exceptions documented.
  - Confirm `HARD_MAX_ORDER_ZAR` env var is set conservatively.

- **Start Canary**:
  - Merge ops branch to main (already merged remotely).
  - Deploy model to canary: place model dir under `models/canary/<model>` and add `baseline_accepted.json` if approved.
  - Start paper trading with `scripts/run_production_smoke.py --model-dir models/canary/<model>` in monitor mode.

  - Note: `regime_confidence` is a known noisy feature and is whitelisted for PSI alerts by default.
    Any ALERTs involving `regime_confidence` require manual triage and cannot be auto-promoted. Prefer using
    `regime_confidence_percentile` or `regime_confidence_smooth_percentile` for automated gating where possible.

- **Monitoring**:
  - Stream logs and watch for PSI ALERT Telegrams.
  - Track `backtest_results/production_smoke_extended.json` and daily summaries.
  - Use kill switch (`scripts/toggle_kill_switch.py`) to pause immediately if anomalies.

- **Stop / Rollback**:
  - Stop process, disable canary model, and remove `baseline_accepted.json`.
  - If necessary, revert merge and open PR for rollback.

- **Post-mortem**:
  - Collect `psi_check.json`, adversarial reports, smoke results, and attach to PR/issue.
  - Triage offending features and plan mitigation: smoothing, winsorize, retrain, or baseline update.

**End of runbook**

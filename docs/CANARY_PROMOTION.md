# Canary Promotion Checklist

1. Preconditions
- CI PSI gate: `backtest_results/ci_psi_report.json` overall_status must be `OK` or `WARN` (WARN requires ops acknowledgment).
- `ops/psi_exceptions.json` must list any whitelisted features with justification in the PR.
- Secrets set: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (for alerts).

2. Promote baseline
- Run: `python scripts/promote_baseline_to_model.py --model-name production_retrained_winsor_quantile_long`
- Confirm `models/production/production_retrained_winsor_quantile_long/psi_baseline.json` exists.

3. Start monitored paper canary
- Run (example):
```
./scripts/run_canary_paper_trading.sh 24
```
- This runs `scripts/run_paper_trading_live.py` in canary mode for 24 hours and logs to `logs/`.

4. Monitoring & alerts
- Watch `backtest_results/` for periodic PSI snapshots and `logs/canary*.log` for runtime errors.
- Telegram alerts will post to configured chat when CI gates fail or when `scripts/notify_telegram.py` is invoked by CI.

5. Rollback
- To stop canary: toggle kill switch `python scripts/toggle_kill_switch.py --off` or terminate run.
- To revert baseline: replace `models/production/<model>/psi_baseline.json` with previous baseline from `ops/promoted_baselines`.

6. Post-run
- Collect telemetry and export: `backtest_results/canary_*.json` and upload to `/backtest_results/reproduction/`.
- Create an incident/retrospective if PSI or runtime alerts occurred.

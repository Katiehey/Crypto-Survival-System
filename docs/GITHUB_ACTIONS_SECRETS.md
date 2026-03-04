# Wiring GitHub Actions secrets for the canary workflow

1) Open your repository on GitHub → Settings → Secrets and variables → Actions → New repository secret.

Required (optional depending on your setup):
- `TELEGRAM_ENABLED` — `true` or `false` (default `false`)
- `TELEGRAM_BOT_TOKEN` — bot token (if `TELEGRAM_ENABLED=true`)
- `TELEGRAM_CHAT_ID` — chat id to receive notifications

Optional helpful secrets:
- `PYPI_API_TOKEN` — if you publish artifacts (not required)

2) Verify the workflow has `workflow_dispatch` so you can run it manually for testing. The workflow added at `.github/workflows/canary_snapshot.yml` already includes a `schedule` trigger; add a manual dispatch via the Actions UI if present.

3) Manually trigger and test the workflow:
- Go to the Actions tab → select `canary_snapshot` (or the name shown) → click `Run workflow` → choose branch `main` and `Run workflow`.
- Inspect the job logs and the uploaded artifacts (artifact named `status` or similar).

4) If you enabled Telegram notifications, check that the workflow log shows a successful POST to the Telegram API. If not, verify the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` values in repo secrets.

5) Local test before pushing secrets (optional):
   - Run `python3 scripts/write_status_snapshot.py --model-dir models/production/production_retrained_winsor_quantile_long` locally to verify snapshot generation.
   - Run `python3 scripts/run_psi_check.py` locally to verify PSI checks.

Security notes:
- Keep bot tokens and chat ids secret.
- Limit repository collaborator access.

If you want, I can create a tiny `scripts/verify_github_secrets.py` that prints masked values from environment (safe to run locally) to help verify your inputs before pushing them to GitHub.

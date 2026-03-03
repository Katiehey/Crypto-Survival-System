Quarantine recommendation: Block promotion — PSI ALERT

Summary
- Trigger: CI smoke + PSI check on branch `clean/pr/ci-psi-monitoring`.
- Recommendation: Quarantine the production model used by this PR until human review.

Key artifacts
- PSI check: (attach or paste link) `psi_check.json`
- Production smoke summary: (attach or paste link) `production_smoke_summary.json`
- CI run: (attach or paste workflow run link)

Findings
- PSI ALERT for feature `efficiency_ratio_smooth` (PSI ≈ 0.34 — ALERT)
- Elevated PSI also observed for `efficiency_ratio` and `volume_ratio` in this run
- Full unit test suite: `316 passed, 4 skipped` (local run)

Impact
- Model promotion risk: reported drift could materially change decisioning. Automated promotion should be blocked until investigation/validation.

Suggested immediate actions
- Apply label `quarantine` to this PR and block automated promotion.
- Create an investigation ticket (template attached in repo) and assign to ML lead or owner.
- Recompute baseline on recent production data and compare per-feature histograms/time-series for `efficiency_ratio_smooth`.
- If drift confirmed: retrain the model or revert to the last validated artifact.

How to reproduce locally
1. Checkout this branch.
2. Ensure venv is active and dependencies installed:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Re-run the PSI check (writes new `models/production/*/psi_check.json`):

```bash
PYTHONPATH=. "/path/to/venv/bin/python" scripts/run_psi_check.py
```

Attachments
- Attach `psi_check.json` and `production_smoke_summary.json` from the CI run.

Signed-off-by: automated PSI guard

Notes for reviewers
- If you need me to attach the artifacts here, I can do that. I can also recompute baseline using different windows if requested.

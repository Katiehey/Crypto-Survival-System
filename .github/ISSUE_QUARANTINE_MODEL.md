Title: Quarantine: PSI ALERT — possible model drift for production model

Description
We detected a PSI ALERT during CI smoke tests indicating distributional drift for production features used by the model. This issue tracks investigation and remediation.

Summary of findings
- Branch: `clean/pr/ci-psi-monitoring`
- PSI ALERT feature: `efficiency_ratio_smooth` (PSI ≈ 0.34)
- Other elevated PSI: `efficiency_ratio`, `volume_ratio`
- Artifacts: `psi_check.json`, `production_smoke_summary.json` (attach from CI run)

Environment
- CI run: (paste workflow run URL)
- Repository: (paste repo URL)

How to reproduce
1. Checkout branch.
2. Run: `PYTHONPATH=. "/path/to/venv/bin/python" scripts/run_psi_check.py`
3. Inspect `models/production/*/psi_check.json` and `production_smoke_summary.json`

Observed
- PSI ALERT for `efficiency_ratio_smooth` and elevated PSI for related features.

Expected
- PSI values within tolerances (no ALERTs) for promoted models.

Impact
- Potential for degraded model decisions in production. Block automated promotion until validated.

Proposed next steps
- [ ] Attach CI artifacts to this issue.
- [ ] Recompute baseline using recent production data and attach comparison plots.
- [ ] Run per-window PSI (7/14/30/90 day) and attach numeric results.
- [ ] If drift confirmed: retrain model and validate on holdout; otherwise document acceptable causes and clear quarantine.

Labels: `quarantine`, `ml/ops`, `investigation`
Priority: `P1`

Assignees: (assign ML owner or on-call)

Notes
- Tests: local test suite passed (`316 passed, 4 skipped`).
- If you want, I can attach the PSI JSON artifacts to this issue or PR comment.

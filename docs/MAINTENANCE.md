# System Maintenance Procedures

This document outlines daily, weekly, and monthly maintenance tasks.

---

## Daily Checks (When System is Running)

### Morning (Before Market Session)
```bash
# 1. Activate environment
source venv/bin/activate

# 2. Check system health
python scripts/health_check.py  # TODO: Create this

# 3. Review overnight logs
tail -n 50 logs/errors/error.log

# 4. Verify capital balance
python scripts/check_balance.py  # TODO: Create this

# 5. Check risk state
# - Consecutive losses < 2?
# - Daily loss < 1%?
# - Kill switch inactive?
```

**Stop trading if**:
- Any errors in overnight logs
- Unexpected capital changes
- Risk limits appear violated

### Evening (After Market Session)
```bash
# 1. Review trade decisions
python scripts/daily_review.py  # TODO: Create this

# 2. Check performance metrics
# - Trades executed today
# - PnL for the day
# - Any limit violations

# 3. Backup database
cp data/trading.db backups/trading_$(date +%Y%m%d).db

# 4. Update CHANGELOG if needed
```

---

## Weekly Maintenance (Sundays)

### Performance Review
```bash
# 1. Run weekly evaluation
python evaluation/weekly_review.py

# 2. Review outputs:
# - Regime classification accuracy
# - Strategy performance by regime
# - Drawdown statistics
# - Fee impact analysis
```

### Code Health
```bash
# 1. Run full test suite
pytest tests/ -v --cov

# 2. Check for code quality issues
black . --check
flake8 .

# 3. Review git history
git log --oneline --since="1 week ago"

# 4. Update dependencies if needed (carefully)
pip list --outdated
```

### Documentation
```bash
# 1. Update CHANGELOG.md
# 2. Review and update README progress
# 3. Add any new decisions to DECISIONS.md
```

---

## Monthly Reviews (First Sunday of Month)

### Deep Performance Analysis

1. **Capital Review**
   - Starting capital vs current
   - Peak capital reached
   - Maximum drawdown
   - Recovery from drawdowns

2. **Strategy Analysis**
   - Which strategies traded most
   - Expectancy by strategy
   - Regime-specific performance
   - Trade frequency analysis

3. **Risk System Audit**
   - Were any limits violated?
   - Are position sizes appropriate?
   - Fee impact on returns
   - Slippage statistics

4. **System Reliability**
   - Uptime percentage
   - Error frequency
   - Data quality issues
   - API rate limit issues

### Decision Points

Ask yourself:

1. **Should I continue trading?**
   - Is capital growing or stable?
   - Is drawdown acceptable?
   - Am I learning from the data?
   - Is stress manageable?

2. **Should I adjust anything?**
   - Strategy enable/disable decisions
   - Data update frequency
   - Logging verbosity
   - **NOT risk limits** (requires full review process)

3. **What did I learn?**
   - Market patterns observed
   - System strengths/weaknesses
   - Personal behavioral patterns
   - Documentation gaps

---

## Emergency Procedures

### System Won't Start
```bash
# 1. Check logs
tail -n 100 logs/errors/error.log

# 2. Verify database integrity
python scripts/verify_db.py  # TODO: Create this

# 3. Test configuration
python config/system_config.py

# 4. Check API connection
python config/exchange_config.py
```

### Unexpected Capital Loss
```bash
# 1. STOP THE SYSTEM IMMEDIATELY
# Kill any running processes

# 2. Check trade history
# Review last 10 trades in database

# 3. Verify exchange account
# Log into Binance, check order history

# 4. Document in incident log
# logs/incidents/YYYYMMDD_incident.txt

# 5. Do NOT restart until cause is found
```

### Kill Switch Activated
```bash
# 1. Document the trigger
# What caused the kill switch?

# 2. Review all recent trades
# Was it legitimate or a bug?

# 3. Fix any issues found

# 4. Wait 48 hours minimum

# 5. Reset kill switch only after review
# Requires manual database update
```

---

## Backup Procedures

### Daily Backups
```bash
# Automated (add to cron/scheduler)
cp data/trading.db backups/daily/trading_$(date +%Y%m%d).db
```

### Weekly Backups
```bash
# Full project backup
tar -czf backups/weekly/project_$(date +%Y%m%d).tar.gz \
  --exclude='venv' \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  .
```

### Before Major Changes
```bash
# Snapshot before any risk limit changes or major refactors
git tag -a "snapshot-$(date +%Y%m%d)" -m "Snapshot before [change description]"
git push --tags

cp data/trading.db backups/snapshots/trading_$(date +%Y%m%d_%H%M).db
```

---

## Monitoring Checklist

### System Health Indicators

✅ **Healthy**:
- Tests passing
- No errors in last 24h
- Capital stable or growing
- Risk limits respected
- Trades executing as expected

⚠️ **Warning**:
- Occasional errors
- Near risk limits
- Unusual regime classifications
- Higher than expected fees

🚨 **Critical**:
- Risk limit violated
- Unexpected capital loss
- System crashes
- API authentication failures
- Kill switch activated

---

## Maintenance Schedule Template
```
WEEK OF: [Date]

Daily:
[ ] Mon - Morning health check, evening review
[ ] Tue - Morning health check, evening review
[ ] Wed - Morning health check, evening review
[ ] Thu - Morning health check, evening review
[ ] Fri - Morning health check, evening review
[ ] Sat - Morning health check, evening review
[ ] Sun - Morning health check, evening review

Weekly:
[ ] Run weekly evaluation
[ ] Full test suite
[ ] Code quality checks
[ ] Update documentation
[ ] Database backup

Notes:
[Any observations, issues, or decisions made this week]
```

---

**Last Updated**: 2026-01-07
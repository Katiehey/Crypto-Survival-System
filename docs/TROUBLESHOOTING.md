# Troubleshooting Guide

Common issues and their solutions.

---

## Installation Issues

### Virtual Environment Won't Activate

**Symptom**: `source venv/bin/activate` does nothing or errors

**Solution**:
```bash
# Delete and recreate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### ImportError: No module named 'ccxt'

**Symptom**: Python can't find installed packages

**Solution**:
```bash
# Verify virtual environment is activated
which python  # Should point to venv/bin/python

# If not, activate it
source venv/bin/activate

# Reinstall packages
pip install -r requirements.txt
```

---

## Configuration Issues

### "Risk limits validation failed"

**Symptom**: System won't start, error about risk limits

**Cause**: Invalid values in `.env` file

**Solution**:
```bash
# Check your .env file
cat .env | grep RISK

# Ensure:
# MAX_RISK_PER_TRADE <= 0.01 (1%)
# MAX_DAILY_LOSS <= 0.02 (2%)
# MAX_TRADES_PER_DAY <= 5

# Reset to defaults if needed
cp .env.example .env
```

### "Binance API credentials not configured"

**Symptom**: Can't connect to exchange

**Solution**:
```bash
# 1. Verify .env file exists
ls -la .env

# 2. Check API keys are set
grep BINANCE_API_KEY .env

# 3. Ensure not using placeholder values
# Keys should NOT be "your_api_key_here"

# 4. Get real API keys from Binance
# https://www.binance.com/en/my/settings/api-management
```

---

## Database Issues

### "database is locked"

**Symptom**: SQLite database won't open

**Cause**: Another process is using the database

**Solution**:
```bash
# 1. Check for other Python processes
ps aux | grep python

# 2. Kill any running trading system
pkill -f "python.*run_"

# 3. If issue persists, restart computer
```

### "no such table: candles"

**Symptom**: Database tables don't exist

**Solution**:
```bash
# Reinitialize database
python scripts/setup_db.py
```

---

## Data Issues

### "Not enough candles for regime classification"

**Symptom**: System won't trade, says insufficient data

**Solution**:
```bash
# Fetch more historical data
python data/fetcher.py --symbol BTC/USDT --timeframe 1h --limit 200

# Verify data exists
python scripts/check_data.py  # TODO: Create this
```

### "NaN values in features"

**Symptom**: Regime classifier produces NaN

**Cause**: Insufficient data or calculation error

**Solution**:
```bash
# 1. Check data quality
python regime/features.py --test

# 2. Ensure enough historical candles
# Need at least MIN_CANDLES_REQUIRED (100)

# 3. Check for gaps in data
# Re-fetch if needed
```

---

## Exchange API Issues

### "binance {"code":-2015,"msg":"Invalid API-key"}"

**Symptom**: Authentication failure

**Solutions**:
1. **Check API key is correct** (copy-paste from Binance)
2. **Verify IP whitelist** (if enabled on Binance)
3. **Check key permissions** (needs "Spot & Margin Trading")
4. **Try testnet first** (set `BINANCE_TESTNET=true`)

### "Rate limit exceeded"

**Symptom**: API calls being rejected

**Solution**:
```bash
# ccxt handles rate limiting automatically
# But if still hitting limits:

# 1. Reduce DATA_UPDATE_INTERVAL in .env
# 2. Add delays between calls
# 3. Check for infinite loops in code
```

---

## Trading Issues

### "Order rejected: insufficient balance"

**Symptom**: Can't place trades

**Cause**: Not enough USDT in account

**Solution**:
```bash
# 1. Check actual balance
python config/exchange_config.py

# 2. Verify STARTING_CAPITAL in .env matches reality

# 3. For testnet, get test funds:
# https://testnet.binance.vision/
```

### "Kill switch activated"

**Symptom**: System stops trading

**Cause**: Drawdown exceeded threshold

**Solution**:
```bash
# 1. This is INTENTIONAL - system protecting you

# 2. Review what happened
python evaluation/weekly_review.py

# 3. Document in logs/incidents/

# 4. Wait minimum 48 hours

# 5. Only reset after understanding cause

# 6. Reset (if appropriate):
# Manual database update required
```

---

## Testing Issues

### Tests Failing After Code Changes

**Symptom**: `pytest` shows failures

**Solution**:
```bash
# 1. Read the error messages carefully

# 2. Run single failing test for clarity
pytest tests/test_specific.py::test_function -v

# 3. Check if test expectations need updating

# 4. NEVER skip tests to "make it work"
# Fix the code or fix the test properly
```

---

## Performance Issues

### System Running Slow

**Symptom**: Takes long time to process

**Solutions**:
1. **Check data volume** - Too much historical data?
2. **Review regime calculations** - Inefficient loops?
3. **Database size** - Consider archiving old data
4. **Not a priority** - This system optimizes for correctness, not speed

---

## When Nothing Works

### Nuclear Option (Use with Caution)
```bash
# 1. Backup everything
cp -r . ../crypto-survival-system-backup

# 2. Fresh start
rm -rf venv
rm data/trading.db

# 3. Rebuild
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/setup_db.py

# 4. Run tests
pytest tests/ -v
```

---

## Getting Help

Since this is a solo project, "getting help" means:

1. **Read the error message carefully**
2. **Check this troubleshooting guide**
3. **Review PHILOSOPHY.md for system principles**
4. **Look at git history** - What changed recently?
5. **Sleep on it** - Often clarity comes with rest
6. **Simplify** - Remove recent changes until it works

**Remember**: If you can't fix it quickly, it's safer to stop trading than to force a fix.

---

**Last Updated**: 2026-01-07
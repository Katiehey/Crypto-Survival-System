# System Philosophy

## Why This System Exists

This system exists because:

1. **Small capital dies from overtrading, not undertrading**  
   With R500, every decision matters. Doing nothing is often the right choice.

2. **Prediction is impossible; preparation is mandatory**  
   This system does not predict prices. It classifies market conditions and responds with predetermined rules.

3. **Emotional trading destroys accounts**  
   By encoding rules in code, we remove the temptation to "just this once" override our limits.

4. **Complexity kills**  
   The more moving parts, the more ways to fail. Simple systems survive.

---

## What Could Go Wrong

### Financial Risks
- **Capital loss**: Even with strict limits, losing trades will occur
- **Fee erosion**: With small capital, exchange fees matter significantly
- **Slippage**: Market orders can execute worse than expected
- **Black swan events**: Markets can gap beyond stop losses

### Technical Risks
- **API failures**: Exchange downtime or rate limits
- **Bug in risk engine**: A coding error could violate position limits
- **Data quality issues**: Bad data leads to bad decisions
- **Execution errors**: Orders rejected, partial fills

### Psychological Risks
- **Impatience**: Wanting to trade when the system says "no trade"
- **Overconfidence**: Increasing risk after winning streak
- **Revenge trading**: Manually overriding after losses
- **Feature creep**: Adding complexity that reduces reliability

---

## Rules for When to STOP Trading

The system MUST be stopped immediately if:

1. **Drawdown exceeds 5%** from peak capital
2. **Three consecutive losing days**
3. **Any bug discovered in risk calculation**
4. **Exchange API behaves unexpectedly**
5. **Personal financial stress** (need the capital for life expenses)
6. **System feels confusing or out of control**
7. **Temptation to override risk limits**

### Stop Protocol

When stopped:
1. Close all open positions (if any)
2. Document reason for stop in `logs/system_stops.txt`
3. Do NOT restart until:
   - Bug is fixed and tested
   - Written review is completed
   - Minimum 48-hour cooling period has passed

---

## Success Metrics (In Order of Priority)

1. **Survival**: System runs without violating risk limits
2. **Consistency**: System behavior is predictable and reproducible
3. **Learning**: Logs provide clear insight into what worked/didn't
4. **Capital preservation**: Drawdowns stay within acceptable limits
5. **Returns**: Positive returns are a BONUS, not the primary goal

---

## The Boring Manifesto

- Boring systems survive
- Exciting systems blow up
- If it feels clever, it's probably wrong
- If it feels safe, it's probably right
- Missing trades is acceptable
- Missing sleep is not

---

**Remember**: This system's purpose is to keep you in the game long enough to learn, adapt, and compound — not to get rich quickly.

**Last Updated**: 2026-01-07
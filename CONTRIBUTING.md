# Contributing Guidelines

**Important**: This is a PRIVATE, single-operator project. These guidelines exist to keep MYSELF disciplined and consistent.

## Core Principles

### 1. Survival > Cleverness
If a change increases complexity, it needs extraordinary justification.

### 2. Test Everything
No code enters the main branch without tests. Period.

### 3. Document Decisions
Every non-obvious choice gets documented in DECISIONS.md.

### 4. Small, Focused Commits
Each commit should do ONE thing and explain WHY.

---

## Development Workflow

### Branch Strategy
```
main (always shippable)
  ↳ feature/regime-classifier
  ↳ feature/risk-engine
  ↳ fix/data-fetcher-bug
```

**Rules**:
- `main` branch is protected (always working)
- Feature branches for new work
- Bug fixes get their own branches
- Merge only after tests pass

### Commit Message Format
```
<type>: <short summary>

<detailed explanation of WHY this change exists>

<consequences, risks, or related issues>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `test`: Add or modify tests
- `docs`: Documentation only
- `refactor`: Code improvement (no behavior change)
- `risk`: Changes to risk engine (CRITICAL)
- `config`: Configuration changes

**Examples**:
```
feat: Add ATR calculation to regime features

ATR is needed to measure volatility for regime classification.
Using 14-period default, which is standard for crypto.

Related to regime classifier implementation.
```
```
risk: Reduce MAX_RISK_PER_TRADE from 0.5% to 0.4%

After reviewing backtest results, 0.5% risk led to excessive
drawdowns during high volatility periods.

This change reduces maximum single-trade risk.
Requires recalculating position sizes in risk engine.
```

---

## Code Standards

### Python Style
- Follow PEP 8
- Use type hints where possible
- Maximum line length: 100 characters
- Use `black` for formatting: `black .`

### Testing Requirements
- Every function needs at least one test
- Edge cases must be tested (zero, negative, NaN, None)
- Risk calculations need extra validation

### Documentation Requirements
- Docstrings for all public functions
- Inline comments for non-obvious logic
- README updates for new features

---

## What NOT to Do

### ❌ Never
- Commit API keys or secrets
- Push directly to `main`
- Skip tests "just this once"
- Modify risk limits without review process
- Add dependencies without updating requirements.txt
- Use `print()` for logging (use proper logging module)

### ⚠️ Requires Extra Review
- Changes to `config/system_config.py`
- Changes to risk engine
- New dependencies
- Database schema modifications
- Strategy additions

---

## Review Process (Self-Review Checklist)

Before merging any feature branch:
```
[ ] All tests pass
[ ] New code has tests
[ ] Documentation updated
[ ] CHANGELOG.md updated
[ ] No secrets in code
[ ] Risk limits not violated
[ ] Change logged in DECISIONS.md (if architectural)
[ ] Can explain WHY this change exists
```

---

## Risk Limit Modification Process

Changing risk limits is SERIOUS. Follow this:

1. **Document reasoning** in DECISIONS.md
2. **Run backtests** with new limits
3. **Paper trade** for minimum 2 weeks
4. **Review results** objectively
5. **Sleep on it** for 48 hours
6. **Commit with detailed explanation**

Example acceptable reasons:
- Backtests show lower risk improves survival
- Fee structure requires adjustment
- Capital increased significantly

Example UNACCEPTABLE reasons:
- "Want to make more money"
- "System is too slow"
- "Feeling confident"

---

## When to Stop Developing

Stop immediately if:
- You're frustrated or emotional
- You want to "quickly fix" something in production
- Tests are failing but you want to push anyway
- You're thinking "I'll test it later"
- You're working past midnight
- You skipped proper meals to keep coding

**Remember**: This system exists to keep you alive in markets. Don't let development pressure create production risks.

---

## Questions to Ask Yourself

Before any significant change:

1. Does this make the system MORE survivable?
2. Can I explain this to myself in 6 months?
3. Does this add complexity I can maintain?
4. What's the worst that could happen?
5. Am I doing this for the right reasons?

If answers are unclear → don't do it yet.

---

**Last Updated**: 2026-01-07
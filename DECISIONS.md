# Architectural Decision Log

This file records significant decisions made during system development.

Format:
- **Date**: When decision was made
- **Decision**: What was decided
- **Context**: Why this decision was needed
- **Consequences**: What this means for the system
- **Status**: Active, Superseded, or Deprecated

---

## ADR-001: Use SQLite for Data Storage

**Date**: 2026-01-07  
**Status**: Active

**Decision**: Use SQLite as the primary database for all system data.

**Context**:
- Small scale operation (single user, single machine)
- Need for simplicity and reliability
- No concurrent access requirements
- Easy backup (single file)

**Alternatives Considered**:
- PostgreSQL: Overkill for this scale
- CSV files: Hard to query, no ACID guarantees
- MongoDB: Unnecessary complexity

**Consequences**:
- ✅ Simple setup (no server required)
- ✅ Easy backup and versioning
- ✅ Built into Python standard library
- ⚠️ Limited to single-machine deployment
- ⚠️ No built-in replication

---

## ADR-002: Freeze Risk Limits in Code

**Date**: 2026-01-07  
**Status**: Active

**Decision**: Implement risk limits as frozen dataclasses, making them immutable at runtime.

**Context**:
- Risk limits are the CORE safety mechanism
- Must prevent accidental modification during execution
- Need to enforce review process for changes

**Implementation**:
```python
@dataclass(frozen=True)
class RiskLimits:
    MAX_RISK_PER_TRADE: float = 0.005
    # ...
```

**Consequences**:
- ✅ Cannot be modified accidentally
- ✅ Clear audit trail (git commits required)
- ✅ Forces deliberate decision-making
- ⚠️ Requires code change to adjust (this is intentional)

---

## ADR-003: AI as Offline Supervisor Only

**Date**: 2026-01-07  
**Status**: Active

**Decision**: AI components can only classify regimes and evaluate performance offline. AI cannot place trades, adjust position sizes, or modify risk parameters.

**Context**:
- Small capital makes errors catastrophic
- AI predictions are unreliable
- Need human accountability for capital decisions
- System must be explainable

**AI Permitted**:
- Regime classification (trend/range/chaos)
- Weekly performance review
- Strategy effectiveness evaluation

**AI Forbidden**:
- Trade entry/exit decisions
- Position sizing
- Stop loss placement
- Risk limit adjustments
- Real-time parameter optimization

**Consequences**:
- ✅ System remains understandable
- ✅ Clear accountability
- ✅ Predictable behavior
- ⚠️ May miss "optimal" entries (acceptable trade-off)

---

## ADR-004: Single Trading Pair Initially

**Date**: 2026-01-07  
**Status**: Active

**Decision**: Trade only BTC/USDT initially. No portfolio diversification.

**Context**:
- R500 starting capital is too small for diversification
- Need to master one market before expanding
- Simpler system = fewer failure modes

**Consequences**:
- ✅ Focused learning
- ✅ Simpler code
- ✅ Lower cognitive load
- ⚠️ Single point of failure (BTC-specific risks)
- 📝 May expand to ETH/USDT after 6 months of stability

---

## ADR-005: Paper Trading Mandatory Before Live

**Date**: 2026-01-07  
**Status**: Active

**Decision**: Minimum 2 weeks of stable paper trading required before any live trading.

**Context**:
- Need to discover execution bugs in safe environment
- Need to validate risk engine works correctly
- Need to build confidence in system behavior

**Criteria for Graduating to Live**:
1. Paper trading runs for ≥14 days without crashes
2. Risk limits never violated
3. Regime classifier produces sensible outputs
4. No bugs discovered in last 7 days
5. All tests passing
6. Manual review completed

**Consequences**:
- ✅ Safer transition to live trading
- ✅ Builds operator confidence
- ⚠️ Delays live deployment (acceptable)

---

## ADR-006: Limit Orders Over Market Orders

**Date**: 2026-01-07  
**Status**: Active

**Decision**: Use limit orders by default to control slippage.

**Context**:
- Small capital makes fees critical
- Market orders have unpredictable execution prices
- Willing to miss some trades for better prices

**Implementation**:
- Place limit orders at current bid/ask
- Cancel if not filled within reasonable time
- Accept that some opportunities will be missed

**Consequences**:
- ✅ Lower fees (maker vs taker)
- ✅ Predictable execution prices
- ⚠️ Some trades won't fill
- ⚠️ More complex execution logic

---

## Template for New Decisions
```markdown
## ADR-XXX: [Decision Title]

**Date**: YYYY-MM-DD  
**Status**: Active | Superseded | Deprecated

**Decision**: [What was decided]

**Context**: [Why this decision was needed]

**Alternatives Considered**:
- Option A: [why not chosen]
- Option B: [why not chosen]

**Consequences**:
- ✅ Positive consequence
- ⚠️ Trade-off or limitation
- ❌ Negative consequence (if any)

**Related**: ADR-XXX, ADR-YYY
```

---

**Last Updated**: 2026-01-07
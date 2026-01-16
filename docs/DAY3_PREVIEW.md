# Day 3 Preview: Regime Classifier

**Goal**: Build rule-based regime classifier using calculated features

---

## What We'll Build

### Regime Types (4)

1. **TREND** - Strong directional movement
   - High efficiency (>0.6)
   - Moderate to high volume
   - Any volatility

2. **RANGE** - Sideways consolidation
   - Low efficiency (<0.3)
   - Low volatility (ATR < 30th percentile)
   - Normal volume

3. **CHAOS** - High volatility without direction
   - Low efficiency (<0.3)
   - High volatility (ATR > 70th percentile)
   - Any volume

4. **NO_TRADE** - Unclear or dangerous conditions
   - Missing data
   - Extreme readings
   - Contradictory signals

### Confidence Scoring

Each regime classification includes confidence (0-1):
- 1.0 = All indicators strongly agree
- 0.7 = Most indicators agree
- 0.5 = Weak signals
- <0.5 = Conflicting signals (→ NO_TRADE)

---

## Structure (5 Pomodoros)

### Pomodoro 11: Regime Classification Logic
- Define regime rules
- Implement classifier function
- Basic tests

### Pomodoro 12: Confidence Scoring
- Multi-factor confidence calculation
- Weighting logic
- Edge case handling

### Pomodoro 13: Regime Integration
- Add regime features to pipeline
- Validation logic
- Integration tests

### Pomodoro 14: Regime Visualization
- Create plotting script
- Regime statistics
- Transition analysis

### Pomodoro 15: Day 3 Review
- Complete test suite
- Documentation update
- Week 1 preparation

---

## Key Decisions to Make

1. **Threshold values**
   - What ER = strong trend? (Proposal: >0.6)
   - What ATR% = high volatility? (Proposal: >70th percentile)

2. **Confidence weighting**
   - How much weight to efficiency vs ATR vs volume?
   - Proposal: ER=50%, ATR=30%, Volume=20%

3. **Minimum confidence**
   - Below what confidence = NO_TRADE?
   - Proposal: <0.4

---

## Expected Output

By end of Day 3:
- Regime classifier function
- 15+ new tests
- Regime visualization script
- Documentation updated
- Ready for Week 1 integration (Day 4-5)

---


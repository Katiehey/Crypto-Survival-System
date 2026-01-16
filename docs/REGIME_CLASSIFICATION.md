# Regime Classification Documentation

## Overview

The regime classification system identifies four distinct market states based on calculated features.

---

## Regime Types

### 1. TREND (Directional Movement)

**Characteristics**:
- High Efficiency Ratio (≥0.6)
- Normal or high volume
- Any volatility level

**Trading Implications**:
- ✅ Tradable
- Trend-following strategies work well
- Clear directional bias
- High confidence when volume supports

**Example Conditions**:
- ER = 0.75, ATR %ile = 50, Volume = normal
- ER = 0.80, ATR %ile = 70, Volume = high

---

### 2. RANGE (Consolidation)

**Characteristics**:
- Low Efficiency Ratio (<0.35)
- Low volatility (ATR < 40th percentile)
- Normal or low volume

**Trading Implications**:
- ✅ Tradable (with appropriate strategy)
- Mean-reversion strategies work
- Support/resistance levels matter
- Lower confidence than trends

**Example Conditions**:
- ER = 0.20, ATR %ile = 25, Volume = normal
- ER = 0.30, ATR %ile = 35, Volume = low

---

### 3. CHAOS (Whipsaw)

**Characteristics**:
- Low Efficiency Ratio (<0.35)
- High volatility (ATR ≥ 60th percentile)
- Any volume

**Trading Implications**:
- ❌ Not tradable
- High volatility without direction
- Stop losses likely to be hit
- Avoid trading until conditions clarify

**Example Conditions**:
- ER = 0.15, ATR %ile = 85, Volume = high
- ER = 0.25, ATR %ile = 75, Volume = normal

---

### 4. NO_TRADE (Unclear Conditions)

**Characteristics**:
- Missing or invalid data
- Very low volume (<20th percentile)
- Ambiguous feature combinations
- Low confidence (<0.4)

**Trading Implications**:
- ❌ Not tradable
- Conditions unclear or dangerous
- Wait for better setup
- System self-protection

**Example Conditions**:
- Any features with NaN values
- Volume %ile = 10 (very low)
- ER = 0.45 (ambiguous, between thresholds)

---

## Confidence Scoring

Each regime classification includes a confidence score (0-1):

**High Confidence (0.7-1.0)**:
- All indicators strongly agree
- Clear market conditions
- Safe to consider trading

**Medium Confidence (0.4-0.7)**:
- Most indicators agree
- Some ambiguity
- Trade with caution

**Low Confidence (<0.4)**:
- Conflicting signals
- Unclear conditions
- Classified as NO_TRADE

---

## Classification Thresholds
```python
EFFICIENCY_TREND_THRESHOLD = 0.6      # ER >= 0.6 = strong trend
EFFICIENCY_RANGE_THRESHOLD = 0.35     # ER < 0.35 = no trend

ATR_HIGH_PERCENTILE = 60              # ATR > 60th %ile = high vol
ATR_LOW_PERCENTILE = 40               # ATR < 40th %ile = low vol

VOLUME_LOW_PERCENTILE = 20            # Vol < 20th %ile = very low

MIN_CONFIDENCE_TRADABLE = 0.4         # Below this = NO_TRADE
```

---

## Regime Transitions

### Common Transitions

**TREND → RANGE**:
- Directional movement exhausts
- Price enters consolidation
- Volume typically decreases

**RANGE → TREND**:
- Breakout from consolidation
- Volume surge
- Efficiency increases

**TREND/RANGE → CHAOS**:
- Volatility spike without direction
- Often during news events
- Temporary (usually resolves)

**CHAOS → Any**:
- Volatility settles
- Direction emerges (→TREND)
- Or volatility drops (→RANGE)

### Persistence

Average regime durations (from backtesting):
- TREND: 8-15 periods (8-15 hours on 1h timeframe)
- RANGE: 10-20 periods
- CHAOS: 3-8 periods (shortest)
- NO_TRADE: Variable

---

## Usage Examples

### Check Current Regime
```python
from data.fetcher import DataFetcher
from regime.features import calculate_complete_pipeline

fetcher = DataFetcher()
df = fetcher.load_candles(limit=200)
df = calculate_complete_pipeline(df)

current = df.iloc[-1]
print(f"Regime: {current['regime']}")
print(f"Confidence: {current['regime_confidence']:.2f}")
print(f"Tradable: {current['regime_tradable']}")
```

### Analyze Regime History
```python
from regime.visualization import analyze_regime_sequence

analysis = analyze_regime_sequence(df)
print(f"Transition rate: {analysis['transition_rate']:.1%}")
print(f"Mean TREND duration: {analysis['duration_stats']['trend']['mean']:.1f}")
```

### Filter for Tradable Periods
```python
tradable = df[df['regime_tradable'] == True]
print(f"Tradable periods: {len(tradable)} / {len(df)}")
```

---

## Validation

All regime classifications are validated:
- Regime values must be valid (trend/range/chaos/no_trade)
- Confidence scores in [0, 1]
- Tradable flags must be boolean
- Invalid data triggers NO_TRADE classification

---

## Future Improvements

Potential enhancements (not yet implemented):
- AI-assisted confidence scoring
- Regime prediction (next likely regime)
- Adaptive thresholds based on market conditions
- Multi-timeframe regime analysis

**Note**: Current system is rule-based only. No AI in classification logic yet.

---

**Last Updated**: 2026-01-07
# Feature Engineering Documentation

This document describes all features calculated by the system for regime classification.

---

## Feature Categories

The system calculates three categories of features:

1. **Volatility Features** (ATR family)
2. **Trend Features** (Efficiency Ratio family)
3. **Volume Features** (Volume participation family)

---

## 1. Volatility Features (ATR)

### True Range (tr)
**Purpose**: Measure single-period volatility  
**Formula**: Max of (High-Low, |High-PrevClose|, |Low-PrevClose|)  
**Range**: 0 to infinity (in price units)

### Average True Range (atr)
**Purpose**: Smoothed volatility measure  
**Formula**: Exponential MA of True Range (14-period default)  
**Range**: 0 to infinity (in price units)  
**Interpretation**:
- Higher ATR = More volatile market
- Lower ATR = Calmer market

### ATR Percentage (atr_pct)
**Purpose**: Volatility normalized by price  
**Formula**: ATR / Close Price  
**Range**: 0 to 1 (typically 0.001 to 0.05)  
**Interpretation**:
- 0.01 (1%) = Low volatility
- 0.02 (2%) = Moderate volatility
- 0.03+ (3%+) = High volatility

### ATR Percentile (atr_percentile)
**Purpose**: Context for current volatility  
**Formula**: Percentile rank of ATR over 100-period window  
**Range**: 0 to 100  
**Interpretation**:
- 0-20 = Historically low volatility
- 40-60 = Average volatility
- 80-100 = Historically high volatility

---

## 2. Trend Features (Efficiency Ratio)

### Efficiency Ratio (efficiency_ratio)
**Purpose**: Measure trend strength  
**Formula**: |Net Price Change| / Sum of |Price Changes|  
**Range**: 0 to 1  
**Interpretation**:
- 1.0 = Perfect trend (straight line)
- 0.7+ = Strong trend
- 0.4-0.7 = Moderate trend
- 0.2-0.4 = Weak trend
- <0.2 = No trend (pure noise)

### Smoothed Efficiency Ratio (efficiency_ratio_smooth)
**Purpose**: Reduce noise in efficiency measurement  
**Formula**: 5-period SMA of efficiency_ratio  
**Range**: 0 to 1  
**Use**: More stable than raw efficiency ratio

### Efficiency Percentile (efficiency_percentile)
**Purpose**: Context for current trend strength  
**Formula**: Percentile rank over 100-period window  
**Range**: 0 to 100

### Trend Strength (trend_strength)
**Purpose**: Categorical trend classification  
**Values**:
- 'strong_trend': ER >= 0.7
- 'moderate_trend': 0.4 <= ER < 0.7
- 'weak_trend': 0.2 <= ER < 0.4
- 'no_trend': ER < 0.2

---

## 3. Volume Features

### Volume Moving Average (volume_ma)
**Purpose**: Average volume baseline  
**Formula**: 20-period SMA of volume  
**Use**: Reference for "normal" volume

### Volume Ratio (volume_ratio)
**Purpose**: Current volume relative to average  
**Formula**: Current Volume / Volume MA  
**Range**: 0 to infinity (typically 0.2 to 3.0)  
**Interpretation**:
- <0.5 = Low volume
- 0.5-1.5 = Normal volume
- 1.5-2.0 = High volume
- 2.0+ = Very high volume (spike)

### Volume Percentile (volume_percentile)
**Purpose**: Context for current volume  
**Formula**: Percentile rank over 100-period window  
**Range**: 0 to 100

### Volume Regime (volume_regime)
**Purpose**: Categorical volume classification  
**Values**:
- 'very_high': ratio >= 2.0
- 'high': 1.5 <= ratio < 2.0
- 'normal': 0.5 <= ratio < 1.5
- 'low': ratio < 0.5

### Volume Spike (volume_spike)
**Purpose**: Detect unusual volume events  
**Formula**: Boolean (volume_ratio >= 2.0)  
**Use**: Identify potential breakouts or capitulation

---

## Feature Calculation Pipeline

### Usage
```python
from data.fetcher import DataFetcher
from regime.features import calculate_all_features

# Load data
fetcher = DataFetcher()
df = fetcher.load_candles(limit=200)

# Calculate all features
df = calculate_all_features(df)

# Access features
print(df[['close', 'atr_pct', 'efficiency_ratio', 'volume_ratio']].tail())
```

### Parameters

- `atr_period`: ATR calculation period (default: 14)
- `efficiency_period`: Efficiency ratio period (default: 10)
- `volume_ma_period`: Volume MA period (default: 20)
- `percentile_lookback`: Lookback for percentiles (default: 100)

---

## Feature Validation

All features are validated to ensure:
- No negative values (where inappropriate)
- No infinite values
- Values within expected ranges
- Percentiles in [0, 100]

---

## Feature Interpretation for Regime Classification

### Strong Trending Market
- High efficiency_ratio (>0.7)
- Normal or high volume_ratio
- Any ATR level

### Ranging/Choppy Market
- Low efficiency_ratio (<0.3)
- High ATR (volatility without direction)
- Normal volume

### Dead/Quiet Market
- Low efficiency_ratio
- Low ATR
- Low volume

### Chaotic Market
- Very high ATR (>80th percentile)
- Low efficiency_ratio
- Unpredictable volume

---

**Last Updated**: 2026-01-07
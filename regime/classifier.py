"""
Market regime classifier with Hysteresis (State Memory).

Classifies market conditions based on ATR, Efficiency Ratio, and Volume.
Uses 'sticky' thresholds to prevent rapid regime flipping.
"""

from enum import Enum
from typing import Tuple, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np


class Regime(Enum):
    """Market regime types."""
    TREND = "trend"
    RANGE = "range"
    CHAOS = "chaos"
    NO_TRADE = "no_trade"


@dataclass
class RegimeClassification:
    """Result of regime classification."""
    regime: Regime
    confidence: float
    tradable: bool
    reasons: list[str]
    
    def __repr__(self):
        """Return a string representation of the classification."""
        return (f"RegimeClassification(regime={self.regime.value}, "
                f"confidence={self.confidence:.2f}, tradable={self.tradable})")


class RegimeClassifier:
    """
    Rule-based market regime classifier with State Memory.
    """
    
    # --- HYSTERESIS THRESHOLDS (The "Sticky" Logic) ---
    # TREND: Need 0.65 to start, but only 0.50 to stay in it.
    ER_TREND_ENTRY = 0.65    
    ER_TREND_HOLD  = 0.50     
    
    # RANGE: Need < 0.30 to enter, but stays range up to 0.40.
    ER_RANGE_ENTRY = 0.30     
    ER_RANGE_HOLD  = 0.40     
    
    ATR_HIGH_PERCENTILE = 60              
    ATR_LOW_PERCENTILE = 40               
    VOLUME_LOW_PERCENTILE = 10            
    MIN_CONFIDENCE_TRADABLE = 0.4         

    def __init__(self):
        """Initialize with memory of the last regime."""
        self.last_regime = Regime.NO_TRADE
    
    def classify_regime(
        self,
        efficiency_ratio: float,
        atr_percentile: float,
        volume_percentile: float,
        volume_regime: str
    ) -> RegimeClassification:
        """Classify market regime using state memory."""
        reasons = []
        
        # 1. Check for invalid data
        if self._has_invalid_data(efficiency_ratio, atr_percentile, volume_percentile):
            self.last_regime = Regime.NO_TRADE
            return RegimeClassification(Regime.NO_TRADE, 0.0, False, ["Invalid data"])
        
        # 2. Volume Filter (Survival Rule)
        # Treat values equal to the low-percentile threshold as low volume as well.
        if volume_percentile <= self.VOLUME_LOW_PERCENTILE:
            reasons.append(f"Low volume ({volume_percentile:.1f}%)")
            self.last_regime = Regime.NO_TRADE
            return RegimeClassification(Regime.NO_TRADE, 0.3, False, reasons)

        # 3. Determine TREND state
        # If we were already in a trend, use the lower 'HOLD' threshold
        if self.last_regime == Regime.TREND:
            is_trend = efficiency_ratio >= self.ER_TREND_HOLD
            reasons.append(f"Holding Trend (ER={efficiency_ratio:.2f})")
        else:
            is_trend = efficiency_ratio >= self.ER_TREND_ENTRY
            if is_trend: reasons.append(f"Entered Trend (ER={efficiency_ratio:.2f})")

        if is_trend:
            self.last_regime = Regime.TREND
            conf = min(0.6 + (efficiency_ratio * 0.4), 1.0)
            return RegimeClassification(Regime.TREND, conf, True, reasons)

        # 4. Determine RANGE state
        if self.last_regime == Regime.RANGE:
            is_range = (efficiency_ratio < self.ER_RANGE_HOLD and atr_percentile < self.ATR_LOW_PERCENTILE)
            reasons.append("Holding Range")
        else:
            is_range = (efficiency_ratio < self.ER_RANGE_ENTRY and atr_percentile < self.ATR_LOW_PERCENTILE)
            if is_range: reasons.append("Entered Range")

        if is_range:
            self.last_regime = Regime.RANGE
            return RegimeClassification(Regime.RANGE, 0.6, True, reasons)

        # 5. Determine CHAOS state
        if efficiency_ratio < self.ER_RANGE_HOLD and atr_percentile >= self.ATR_HIGH_PERCENTILE:
            reasons.append("High volatility/Low efficiency")
            self.last_regime = Regime.CHAOS
            return RegimeClassification(Regime.CHAOS, 0.5, False, reasons)

        # 6. Fallback to NO_TRADE
        reasons.append("Ambiguous conditions")
        self.last_regime = Regime.NO_TRADE
        return RegimeClassification(Regime.NO_TRADE, 0.2, False, reasons)

    def classify_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify entire dataframe sequentially to maintain memory."""
        required_cols = ['efficiency_ratio', 'atr_percentile', 'volume_percentile', 'volume_regime']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Missing required columns: {required_cols}")
        
        df = df.copy()
        regimes, confidences, tradables = [], [], []
        
        # IMPORTANT: Reset memory before processing a new batch of history
        self.last_regime = Regime.NO_TRADE

        for _, row in df.iterrows():
            res = self.classify_regime(
                row['efficiency_ratio'], row['atr_percentile'], 
                row['volume_percentile'], row['volume_regime']
            )
            regimes.append(res.regime.value)
            confidences.append(res.confidence)
            tradables.append(res.tradable)
        
        df['regime'] = regimes
        df['regime_confidence'] = confidences
        df['regime_tradable'] = tradables
        return df

    def _has_invalid_data(self, er, atr, vol) -> bool:
        """
        Validate input metrics for NaN, infinity, or logical range violations.
        
        Checks if any input is non-numeric or if the Efficiency Ratio (ER) 
        falls outside the required [0, 1] bounds.
        
        Returns:
            bool: True if data is invalid and classification should be skipped.
        """
        if any(pd.isna([er, atr, vol])) or any(np.isinf([er, atr, vol])):
            return True
    
        # NEW: Check for logical range violations (ER must be between 0 and 1)
        if er < 0 or er > 1:
            return True
        
        return False


def get_regime_statistics(df: pd.DataFrame) -> dict:
    """
    Get statistics about regime classifications.
    
    Args:
        df: DataFrame with regime classifications
        
    Returns:
        Dictionary with regime statistics
    """
    if 'regime' not in df.columns:
        return {}
    
    stats = {
        'total_periods': len(df),
        'regime_counts': df['regime'].value_counts().to_dict(),
        'regime_percentages': (df['regime'].value_counts() / len(df) * 100).to_dict(),
    }
    
    if 'regime_confidence' in df.columns:
        stats['mean_confidence'] = df['regime_confidence'].mean()
        stats['confidence_by_regime'] = df.groupby('regime')['regime_confidence'].mean().to_dict()
    
    if 'regime_tradable' in df.columns:
        stats['tradable_periods'] = df['regime_tradable'].sum()
        stats['tradable_percentage'] = df['regime_tradable'].sum() / len(df) * 100
    
    return stats


def main():
    """
    Run diagnostic tests on the RegimeClassifier using predefined market scenarios.
    
    Tests the logic for Trend, Range, Chaos, and Low Volume states, 
    verifying that the Hysteresis and Volume filters trigger correctly.
    """
    print("=" * 60)
    print("REGIME CLASSIFIER TEST")
    print("=" * 60)
    
    classifier = RegimeClassifier()
    
    # Test scenarios
    scenarios = [
        {
            'name': 'Strong Trend',
            'efficiency_ratio': 0.8,
            'atr_percentile': 50,
            'volume_percentile': 60,
            'volume_regime': 'normal'
        },
        {
            'name': 'Quiet Range',
            'efficiency_ratio': 0.2,
            'atr_percentile': 25,
            'volume_percentile': 40,
            'volume_regime': 'normal'
        },
        {
            'name': 'Chaotic Market',
            'efficiency_ratio': 0.15,
            'atr_percentile': 85,
            'volume_percentile': 70,
            'volume_regime': 'high'
        },
        {
            'name': 'Very Low Volume',
            'efficiency_ratio': 0.5,
            'atr_percentile': 50,
            'volume_percentile': 10,
            'volume_regime': 'low'
        },
        {
            'name': 'Ambiguous',
            'efficiency_ratio': 0.45,
            'atr_percentile': 50,
            'volume_percentile': 50,
            'volume_regime': 'normal'
        }
    ]
    
    print("\nTest Scenarios:")
    print("-" * 60)
    
    for scenario in scenarios:
        name = scenario.pop('name')
        result = classifier.classify_regime(**scenario)
        
        print(f"\n{name}:")
        print(f"  Regime: {result.regime.value}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Tradable: {result.tradable}")
        print(f"  Reasons: {', '.join(result.reasons)}")
    
    print("\n" + "=" * 60)
    print("✅ Regime classifier test complete")


if __name__ == "__main__":
    main()
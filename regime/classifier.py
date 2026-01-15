"""
Market regime classifier.

Classifies market conditions based on calculated features:
- ATR (volatility)
- Efficiency Ratio (trend strength)
- Volume (participation)

Outputs one of four regimes:
- TREND: Strong directional movement
- RANGE: Sideways consolidation
- CHAOS: High volatility without direction
- NO_TRADE: Unclear or dangerous conditions
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
    """
    Result of regime classification.
    
    Attributes:
        regime: Classified regime type
        confidence: Confidence score (0-1)
        tradable: Whether regime is tradable
        reasons: List of reasons for classification
    """
    regime: Regime
    confidence: float
    tradable: bool
    reasons: list[str]
    
    def __repr__(self):
        return (f"RegimeClassification(regime={self.regime.value}, "
                f"confidence={self.confidence:.2f}, tradable={self.tradable})")


class RegimeClassifier:
    """
    Rule-based market regime classifier.
    
    Uses technical indicators to classify market into one of four regimes.
    """
    
    # Classification thresholds
    EFFICIENCY_TREND_THRESHOLD = 0.6      # ER >= 0.6 = strong trend
    EFFICIENCY_RANGE_THRESHOLD = 0.35     # ER < 0.35 = no trend
    
    ATR_HIGH_PERCENTILE = 60              # ATR > 60th %ile = high volatility
    ATR_LOW_PERCENTILE = 40               # ATR < 40th %ile = low volatility
    
    VOLUME_LOW_PERCENTILE = 20            # Volume < 20th %ile = very low
    
    MIN_CONFIDENCE_TRADABLE = 0.4         # Below this = NO_TRADE
    
    def __init__(self):
        """Initialize regime classifier."""
        pass
    
    def classify_regime(
        self,
        efficiency_ratio: float,
        atr_percentile: float,
        volume_percentile: float,
        volume_regime: str
    ) -> RegimeClassification:
        """
        Classify market regime based on features.
        
        Args:
            efficiency_ratio: Efficiency ratio (0-1)
            atr_percentile: ATR percentile (0-100)
            volume_percentile: Volume percentile (0-100)
            volume_regime: Volume regime classification
            
        Returns:
            RegimeClassification with regime, confidence, and reasons
        """
        reasons = []
        
        # Check for invalid data first
        if self._has_invalid_data(efficiency_ratio, atr_percentile, volume_percentile):
            return RegimeClassification(
                regime=Regime.NO_TRADE,
                confidence=0.0,
                tradable=False,
                reasons=["Invalid or missing data"]
            )
        
        # Check for very low volume (usually avoid)
        if volume_percentile < self.VOLUME_LOW_PERCENTILE:
            reasons.append(f"Very low volume ({volume_percentile:.1f}th percentile)")
            return RegimeClassification(
                regime=Regime.NO_TRADE,
                confidence=0.3,
                tradable=False,
                reasons=reasons
            )
        
        # Classify based on feature combinations
        
        # TREND: Strong efficiency + decent volume
        if efficiency_ratio >= self.EFFICIENCY_TREND_THRESHOLD:
            reasons.append(f"Strong trend (ER={efficiency_ratio:.2f})")
            
            # Higher confidence with normal/high volume
            if volume_regime in ['normal', 'high', 'very_high']:
                reasons.append(f"Good volume participation ({volume_regime})")
                confidence = 0.8 + (efficiency_ratio - self.EFFICIENCY_TREND_THRESHOLD) * 0.5
            else:
                reasons.append(f"Low volume ({volume_regime})")
                confidence = 0.6
            
            confidence = min(confidence, 1.0)
            
            return RegimeClassification(
                regime=Regime.TREND,
                confidence=confidence,
                tradable=True,
                reasons=reasons
            )
        
        # RANGE: Low efficiency + low volatility
        if (efficiency_ratio < self.EFFICIENCY_RANGE_THRESHOLD and
            atr_percentile < self.ATR_LOW_PERCENTILE):
            reasons.append(f"Low trend strength (ER={efficiency_ratio:.2f})")
            reasons.append(f"Low volatility (ATR {atr_percentile:.1f}th percentile)")
            
            # Confidence based on how stable the range is
            confidence = 0.5 + (self.EFFICIENCY_RANGE_THRESHOLD - efficiency_ratio) * 0.5
            confidence = min(confidence, 0.8)
            
            return RegimeClassification(
                regime=Regime.RANGE,
                confidence=confidence,
                tradable=True,  # Ranges can be traded with appropriate strategy
                reasons=reasons
            )
        
        # CHAOS: Low efficiency + high volatility
        if (efficiency_ratio < self.EFFICIENCY_RANGE_THRESHOLD and
            atr_percentile >= self.ATR_HIGH_PERCENTILE):
            reasons.append(f"No directional movement (ER={efficiency_ratio:.2f})")
            reasons.append(f"High volatility (ATR {atr_percentile:.1f}th percentile)")
            
            # Higher volatility = lower confidence (more dangerous)
            confidence = 0.7 - (atr_percentile - self.ATR_HIGH_PERCENTILE) / 100
            confidence = max(confidence, 0.3)
            
            return RegimeClassification(
                regime=Regime.CHAOS,
                confidence=confidence,
                tradable=False,  # Chaotic markets are dangerous
                reasons=reasons
            )
        
        # MODERATE CONDITIONS: Efficiency between thresholds
        # This is an ambiguous zone
        if (self.EFFICIENCY_RANGE_THRESHOLD <= efficiency_ratio < self.EFFICIENCY_TREND_THRESHOLD):
            reasons.append(f"Moderate trend strength (ER={efficiency_ratio:.2f})")
            reasons.append("Ambiguous market conditions")
            
            # Lean towards TREND if higher efficiency, RANGE if lower
            if efficiency_ratio >= 0.5:
                regime = Regime.TREND
                confidence = 0.5
            else:
                regime = Regime.RANGE
                confidence = 0.4
            
            # Low confidence in ambiguous conditions
            return RegimeClassification(
                regime=regime,
                confidence=confidence,
                tradable=(confidence >= self.MIN_CONFIDENCE_TRADABLE),
                reasons=reasons
            )
        
        # FALLBACK: If we get here, conditions are unclear
        reasons.append("Unclear market conditions")
        return RegimeClassification(
            regime=Regime.NO_TRADE,
            confidence=0.2,
            tradable=False,
            reasons=reasons
        )
    
    def _has_invalid_data(
        self,
        efficiency_ratio: float,
        atr_percentile: float,
        volume_percentile: float
    ) -> bool:
        """
        Check if any input data is invalid.
        
        Args:
            efficiency_ratio: Efficiency ratio
            atr_percentile: ATR percentile
            volume_percentile: Volume percentile
            
        Returns:
            True if any data is invalid
        """
        # Check for NaN
        if pd.isna(efficiency_ratio) or pd.isna(atr_percentile) or pd.isna(volume_percentile):
            return True
        
        # Check for infinite
        if np.isinf(efficiency_ratio) or np.isinf(atr_percentile) or np.isinf(volume_percentile):
            return True
        
        # Check for out-of-range values
        if efficiency_ratio < 0 or efficiency_ratio > 1:
            return True
        
        if atr_percentile < 0 or atr_percentile > 100:
            return True
        
        if volume_percentile < 0 or volume_percentile > 100:
            return True
        
        return False
    
    def classify_dataframe(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Classify regime for entire DataFrame.
        
        Adds columns:
        - 'regime': Regime classification
        - 'regime_confidence': Confidence score
        - 'regime_tradable': Boolean tradable flag
        
        Args:
            df: DataFrame with feature columns
            
        Returns:
            DataFrame with regime classification columns added
            
        Raises:
            ValueError: If required columns missing
        """
        required_cols = ['efficiency_ratio', 'atr_percentile', 'volume_percentile', 'volume_regime']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        df = df.copy()
        
        # Initialize result columns
        regimes = []
        confidences = []
        tradables = []
        
        # Classify each row
        for idx, row in df.iterrows():
            classification = self.classify_regime(
                efficiency_ratio=row['efficiency_ratio'],
                atr_percentile=row['atr_percentile'],
                volume_percentile=row['volume_percentile'],
                volume_regime=row['volume_regime']
            )
            
            regimes.append(classification.regime.value)
            confidences.append(classification.confidence)
            tradables.append(classification.tradable)
        
        # Add to DataFrame
        df['regime'] = regimes
        df['regime_confidence'] = confidences
        df['regime_tradable'] = tradables
        
        return df


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
    """Test regime classifier with synthetic data."""
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
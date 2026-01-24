"""
Simple Trend Following Strategy

Strategy logic:
- Only trades in TREND regime
- Enters when trend is strong (high efficiency ratio)
- Exits when trend weakens or regime changes
- Uses ATR for stop loss calculation

This is a simple, robust strategy designed for:
- Small capital (R500)
- Capital preservation
- Clear, testable rules
"""

from typing import Optional
import pandas as pd
import numpy as np

from strategies.base import Strategy, TradingSignal, SignalType
from config.system_config import RISK_LIMITS, SYSTEM_CONFIG


class SimpleTrendStrategy(Strategy):
    """
    Simple trend-following strategy.
    
    Entry Conditions (ALL must be true):
    - Regime = TREND
    - Regime confidence > 0.6
    - Efficiency ratio > 0.65
    - Volume normal or high
    - No current position
    
    Exit Conditions (ANY triggers exit):
    - Regime changes to RANGE or CHAOS
    - Efficiency ratio drops below 0.4
    - Stop loss hit (handled by risk engine)
    
    Parameters:
    - entry_efficiency_threshold: 0.65 (strong trend required)
    - exit_efficiency_threshold: 0.4 (trend weakening)
    - min_regime_confidence: 0.6 (confident classification)
    - stop_loss_atr_multiple: 2.0 (conservative stop)
    """
    
    def __init__(
        self,
        entry_efficiency_threshold: float = 0.65,
        exit_efficiency_threshold: float = 0.4,
        min_regime_confidence: float = 0.6,
        stop_loss_atr_multiple: float = 2.0
    ):
        """
        Initialize simple trend strategy.
        
        Args:
            entry_efficiency_threshold: Min efficiency for entry
            exit_efficiency_threshold: Max efficiency before exit
            min_regime_confidence: Min regime confidence required
            stop_loss_atr_multiple: Stop loss distance in ATR multiples
        """
        super().__init__()
        
        self.entry_efficiency_threshold = entry_efficiency_threshold
        self.exit_efficiency_threshold = exit_efficiency_threshold
        self.min_regime_confidence = min_regime_confidence
        self.stop_loss_atr_multiple = stop_loss_atr_multiple
        
        self.logger.info(
            f"SimpleTrendStrategy initialized: "
            f"entry_eff={entry_efficiency_threshold}, "
            f"exit_eff={exit_efficiency_threshold}"
        )
    
    def generate_signal(
        self,
        data: pd.DataFrame,
        current_position: Optional[str] = None
    ) -> TradingSignal:
        """
        Generate trading signal based on trend conditions.
        
        Args:
            data: DataFrame with OHLCV, features, and regime
            current_position: 'long', 'short', or None
            
        Returns:
            TradingSignal with recommended action
        """
        # Validate data
        self.validate_data(data)
        self._validate_strategy_data(data)
        
        # Get latest data point
        latest = data.iloc[-1]
        
        # Extract values
        regime = latest['regime']
        regime_confidence = latest.get('regime_confidence', 0.0)
        efficiency = latest.get('efficiency_ratio', 0.0)
        volume_regime = latest.get('volume_regime', 'unknown')
        close_price = latest['close']
        atr = latest.get('atr', 0.0)
        
        # If we have a position, check exit conditions
        if current_position == 'long':
            signal = self._check_exit_conditions(
                regime, efficiency, close_price, atr
            )
            if signal:
                self.record_signal(signal)
                return signal
        
        # Check entry conditions (only if no position)
        if current_position is None:
            signal = self._check_entry_conditions(
                regime, regime_confidence, efficiency,
                volume_regime, close_price, atr
            )
            self.record_signal(signal)
            return signal
        
        # Default: hold current position
        signal = TradingSignal(
            signal_type=SignalType.NO_TRADE,
            confidence=0.5,
            entry_price=close_price,
            regime=regime,
            reason="Holding current position, no action needed"
        )
        
        self.record_signal(signal)
        return signal
    
    def _check_entry_conditions(
        self,
        regime: str,
        regime_confidence: float,
        efficiency: float,
        volume_regime: str,
        close_price: float,
        atr: float
    ) -> TradingSignal:
        """
        Check if entry conditions are met.
        
        Returns:
            TradingSignal (LONG or NO_TRADE)
        """
        reasons = []
        
        # Condition 1: Must be in TREND regime
        if regime != 'trend':
            return TradingSignal(
                signal_type=SignalType.NO_TRADE,
                confidence=0.0,
                entry_price=close_price,
                regime=regime,
                reason=f"Wrong regime: {regime} (need: trend)"
            )
        
        reasons.append("✓ TREND regime")
        
        # Condition 2: Regime confidence must be sufficient
        if regime_confidence < self.min_regime_confidence:
            return TradingSignal(
                signal_type=SignalType.NO_TRADE,
                confidence=0.0,
                entry_price=close_price,
                regime=regime,
                reason=f"Low regime confidence: {regime_confidence:.2f} < {self.min_regime_confidence}"
            )
        
        reasons.append(f"✓ Confidence: {regime_confidence:.2f}")
        
        # Condition 3: Efficiency must indicate strong trend
        if efficiency < self.entry_efficiency_threshold:
            return TradingSignal(
                signal_type=SignalType.NO_TRADE,
                confidence=0.0,
                entry_price=close_price,
                regime=regime,
                reason=f"Weak trend: ER={efficiency:.2f} < {self.entry_efficiency_threshold}"
            )
        
        reasons.append(f"✓ Strong trend: ER={efficiency:.2f}")
        
        # Condition 4: Volume should be normal or high
        if volume_regime not in ['normal', 'high', 'very_high']:
            return TradingSignal(
                signal_type=SignalType.NO_TRADE,
                confidence=0.3,
                entry_price=close_price,
                regime=regime,
                reason=f"Low volume: {volume_regime}"
            )
        
        reasons.append(f"✓ Volume: {volume_regime}")
        
        # All conditions met - generate LONG signal
        stop_loss = self._calculate_stop_loss(close_price, atr)
        
        # Calculate confidence based on how strong the signal is
        confidence = self._calculate_entry_confidence(
            efficiency, regime_confidence, volume_regime
        )
        
        return TradingSignal(
            signal_type=SignalType.LONG,
            confidence=confidence,
            entry_price=close_price,
            stop_loss=stop_loss,
            regime=regime,
            reason=f"LONG entry: {', '.join(reasons)}",
            metadata={
                'efficiency': efficiency,
                'volume_regime': volume_regime,
                'atr': atr,
            }
        )
    
    def _check_exit_conditions(
        self,
        regime: str,
        efficiency: float,
        close_price: float,
        atr: float
    ) -> Optional[TradingSignal]:
        """
        Check if exit conditions are met.
        
        Returns:
            TradingSignal (EXIT) if should exit, None otherwise
        """
        # Exit condition 1: Regime changed to unfavorable
        if regime in ['range', 'chaos', 'no_trade']:
            return TradingSignal(
                signal_type=SignalType.EXIT,
                confidence=0.9,
                entry_price=close_price,
                regime=regime,
                reason=f"EXIT: Regime changed to {regime}"
            )
        
        # Exit condition 2: Trend weakening
        if efficiency < self.exit_efficiency_threshold:
            return TradingSignal(
                signal_type=SignalType.EXIT,
                confidence=0.8,
                entry_price=close_price,
                regime=regime,
                reason=f"EXIT: Trend weakening (ER={efficiency:.2f})"
            )
        
        # No exit conditions met
        return None
    
    def _calculate_stop_loss(self, entry_price: float, atr: float) -> float:
        """
        Calculate stop loss price based on ATR while respecting Config limits.
        """
        from config.system_config import RISK_LIMITS
    
        if atr == 0 or np.isnan(atr):
        # Fallback: Use a distance that corresponds to our MAX_POSITION_SIZE
        # If we risk 1% and our max size is 50%, our stop must be at least 2% away.
        # Calculation: Risk% / MaxSize% = 0.01 / 0.50 = 0.02 (2%)
            fallback_pct = RISK_LIMITS.MAX_RISK_PER_TRADE / RISK_LIMITS.MAX_POSITION_SIZE_PERCENT
            return entry_price * (1 - fallback_pct)

    # 1. Calculate the ATR-based stop
        stop_distance = atr * self.stop_loss_atr_multiple
        stop_loss = entry_price - stop_distance
    
    # 2. Calculate the "Minimum Allowed Stop Distance" 
    # This ensures the resulting position size won't exceed our Config's MAX_POSITION_SIZE_PERCENT.
    # Logic: If stop is too tight, position size becomes too large for a spot account.
        min_dist_pct = RISK_LIMITS.MAX_RISK_PER_TRADE / RISK_LIMITS.MAX_POSITION_SIZE_PERCENT
        max_stop_price = entry_price * (1 - min_dist_pct)
    
    # 3. Calculate "Maximum Allowed Stop Distance" (Sanity Cap)
    # Let's say we don't want a stop wider than 10% regardless of ATR.
        min_stop_price = entry_price * 0.90 

    # Apply constraints: 
    # stop_loss cannot be higher than max_stop_price (too tight)
    # stop_loss cannot be lower than min_stop_price (too wide)
        final_stop = max(min_stop_price, min(max_stop_price, stop_loss))
    
        return final_stop
    
    def _calculate_entry_confidence(
        self,
        efficiency: float,
        regime_confidence: float,
        volume_regime: str
    ) -> float:
        """
        Calculate entry signal confidence.
        
        Higher confidence when:
        - Very high efficiency (strong trend)
        - High regime confidence
        - High volume
        
        Args:
            efficiency: Efficiency ratio
            regime_confidence: Regime classification confidence
            volume_regime: Volume regime
            
        Returns:
            Confidence score (0-1)
        """
        # Base confidence from efficiency
        # Map 0.65-1.0 to 0.6-1.0
        eff_confidence = (efficiency - 0.65) / 0.35 * 0.4 + 0.6
        eff_confidence = np.clip(eff_confidence, 0.6, 1.0)
        
        # Adjust for regime confidence
        confidence = eff_confidence * regime_confidence
        
        # Boost for high volume
        if volume_regime == 'high' or volume_regime == 'very_high':
            confidence = min(1.0, confidence * 1.1)
        
        return confidence
    
    def _validate_strategy_data(self, data: pd.DataFrame) -> None:
        """
        Validate that data has strategy-specific columns.
        
        Args:
            data: DataFrame to validate
            
        Raises:
            ValueError: If required columns missing
        """
        required = [
            'efficiency_ratio',
            'atr',
            'regime_confidence',
            'volume_regime'
        ]
        
        missing = [col for col in required if col not in data.columns]
        
        if missing:
            raise ValueError(
                f"Missing strategy-required columns: {missing}. "
                f"Run calculate_complete_pipeline() first."
            )
    
    def get_name(self) -> str:
        """Get strategy name."""
        return "Simple Trend Following"
    
    def is_regime_compatible(self, regime: str) -> bool:
        """
        Check if strategy can trade in regime.
        
        Args:
            regime: Market regime
            
        Returns:
            True if compatible
        """
        # Only trade in TREND regime
        return regime == 'trend'


def main():
    """Test simple trend strategy."""
    print("=" * 60)
    print("SIMPLE TREND STRATEGY TEST")
    print("=" * 60)
    
    # Create test data with trend
    import numpy as np
    
    n = 100
    # Uptrend
    prices = np.linspace(40000, 45000, n) + np.random.randn(n) * 200
    
    df = pd.DataFrame({
        'close': prices,
        'high': prices + 100,
        'low': prices - 100,
        'volume': 100 + np.abs(np.random.randn(n) * 20),
        'regime': ['trend'] * n,
        'regime_confidence': np.random.uniform(0.7, 0.9, n),
        'efficiency_ratio': np.random.uniform(0.65, 0.85, n),
        'atr': np.random.uniform(500, 800, n),
        'volume_regime': ['normal'] * 50 + ['high'] * 50,
    })
    
    strategy = SimpleTrendStrategy()
    
    print(f"\n📊 Strategy: {strategy.get_name()}")
    print(f"   Entry threshold: {strategy.entry_efficiency_threshold}")
    print(f"   Exit threshold: {strategy.exit_efficiency_threshold}")
    
    # Test 1: Entry signal
    print("\n🎯 Test 1: Entry signal (no position)")
    signal = strategy.generate_signal(df, current_position=None)
    
    print(f"   Signal: {signal.signal_type.value}")
    print(f"   Confidence: {signal.confidence:.2f}")
    print(f"   Entry: R{signal.entry_price:.2f}")
    if signal.stop_loss:
        print(f"   Stop: R{signal.stop_loss:.2f}")
        stop_pct = (signal.entry_price - signal.stop_loss) / signal.entry_price * 100
        print(f"   Stop distance: {stop_pct:.2f}%")
    print(f"   Reason: {signal.reason}")
    
    # Test 2: Exit signal
    print("\n🎯 Test 2: Exit signal (with position)")
    # Change to ranging market
    df_exit = df.copy()
    df_exit.iloc[-1, df_exit.columns.get_loc('regime')] = 'range'
    
    signal_exit = strategy.generate_signal(df_exit, current_position='long')
    
    print(f"   Signal: {signal_exit.signal_type.value}")
    print(f"   Confidence: {signal_exit.confidence:.2f}")
    print(f"   Reason: {signal_exit.reason}")
    
    # Test 3: Regime compatibility
    print("\n🎯 Test 3: Regime compatibility")
    for regime in ['trend', 'range', 'chaos', 'no_trade']:
        compatible = strategy.is_regime_compatible(regime)
        symbol = "✓" if compatible else "✗"
        print(f"   {symbol} {regime}: {compatible}")
    
    print("\n" + "=" * 60)
    print("✅ Simple trend strategy test complete")


if __name__ == "__main__":
    main()
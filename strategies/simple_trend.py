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

from fileinput import close
from signal import signal
from kiwisolver import strength
from kiwisolver import strength
from typing import Optional
import pandas as pd
import numpy as np
from scipy import signal

from strategies.base import Strategy, TradingSignal, SignalType
from config.system_config import RISK_LIMITS, SYSTEM_CONFIG
from regime.classifier import Regime, RegimeClassification
from strategies.base import TradingSignal, SignalType


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
        entry_efficiency_threshold: float = 0.25,  # Only strong, directional moves
        exit_efficiency_threshold: float = 0.70,   # Exit before the trend completely dies
        min_regime_confidence: float = 0.60,       # High conviction only
        stop_loss_atr_multiple: float = 3.0,       # Tighter stops for better R:R
        exit_patience: int = 12,                    # Don't wait 10 bars in chaos
        take_profit_multiplier: float = 5.0,
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
        self.bad_regime_count = 0
        self.exit_patience = exit_patience
        self.take_profit_multiplier = take_profit_multiplier # <--- ADD THIS
        self.entry_price = 0.0
        self.highest_price = 0.0 
        self.stop_loss = 0.0 
        self.bar_count = 0
        

        
        self.logger.info(
            f"SimpleTrendStrategy initialized: "
            f"entry_eff={entry_efficiency_threshold}, "
            f"exit_eff={exit_efficiency_threshold}"
        )
    
    def generate_signal(
        self,
        dataframe: pd.DataFrame,
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
        if len(dataframe) < 30:
            return TradingSignal(SignalType.NO_TRADE, 0.0, dataframe.iloc[-1]['close'], reason="Waiting for data")

        current_row = dataframe.iloc[-1]
        regime = str(current_row.get('regime', 'none')).lower()
        close_price = float(current_row['close'])
        atr = float(current_row.get('atr', 0))
        efficiency = float(current_row.get('efficiency_ratio', 0))
        confidence = float(current_row.get('regime_confidence', 0))
        atr_history = dataframe['atr']
        avg_atr = atr_history.rolling(10).mean().iloc[-1]
        is_atr_expanding = atr > avg_atr

    # 2. EXIT LOGIC
        if current_position is not None:
            return self._check_exit_conditions(regime, efficiency, close_price, atr)

    # 3. THE GATEKEEPER (Regime Filter)
    # This returns IMMEDIATELY, preventing the 'UnboundLocalError' below
        if regime != 'trend':
            return TradingSignal(SignalType.NO_TRADE, 0.0, close_price, reason=f"Regime: {regime}")

    # 4. ENTRY LOGIC (Only reached if regime == 'trend')
    # We define 'signal' here so it exists for the 'Bouncer' check below
        raw_strength = current_row.get('trend_strength', 0.0)
        strength = float(raw_strength) if not isinstance(raw_strength, str) else 30.0 

        signal = self._check_entry_conditions(
            regime=regime, confidence=confidence, efficiency=efficiency,
            volume_regime=current_row.get('volume_regime', 'normal'), 
            close=close_price, atr=atr, t_strength=strength, 
            e_smooth=efficiency, v_spike=is_atr_expanding
        )

    # 5. THE BOUNCER (Final Filter)
        if signal.signal_type == SignalType.LONG:
            price_sma = dataframe['close'].tail(20).mean()
            is_trending = strength > 15
            above_sma = close_price > price_sma
        
            if is_trending and above_sma:
            # Setup internal tracking for the trade
                self.entry_price = close_price
                self.stop_loss = signal.stop_loss
                self.highest_price = close_price
                self.bar_count = 0
                return signal
            else:
                fail_reason = f"Filtered -> Str: {strength:.1f}>15 ({is_trending}) | Above SMA: {above_sma}"
                return TradingSignal(SignalType.NO_TRADE, 0.0, close_price, reason=fail_reason)
    
        return signal
    
    def _check_entry_conditions(
        self, 
        regime: str, 
        confidence: float, 
        efficiency: float, 
        volume_regime: str, 
        close: float, 
        atr: float,
        t_strength: float,
        e_smooth: float,
        v_spike: bool
    ) -> TradingSignal:
        """
        Refined Entry Logic with Survival Rules.
        Now matches the 9 arguments passed by generate_signal.
        """
        
        # 1. Regime Filter (Primary Gate)
        if str(regime).strip().lower() != 'trend':
            return TradingSignal(SignalType.NO_TRADE, 0.0, close, reason=f"Regime: {regime}")

        # 2. Efficiency Filter (Survival Rule)
        # Using 0.40 as discussed to catch moves early but filter noise
        if efficiency < self.entry_efficiency_threshold:
            return TradingSignal(SignalType.NO_TRADE, 0.0, close, reason=f"Low Efficiency: {efficiency:.2f}")

        if not v_spike:
            return TradingSignal(SignalType.NO_TRADE, 0.0, close, reason="ATR not expanding")

        # 3. Confidence Filter
        if confidence < self.min_regime_confidence:
             return TradingSignal(SignalType.NO_TRADE, 0.0, close, reason="Low Regime Confidence")

        # 4. Math Check: Ensure ATR is valid for Stop Loss
        if atr <= 0:
            return TradingSignal(SignalType.NO_TRADE, 0.0, close, reason="Invalid ATR")

        # 5. Calculate Stop Loss & Confidence
        stop_loss = self._calculate_stop_loss(close, atr)
        signal_confidence = self._calculate_entry_confidence(efficiency, confidence, volume_regime)

        return TradingSignal(
            signal_type=SignalType.LONG,
            confidence=signal_confidence,
            entry_price=close,
            stop_loss=stop_loss,
            reason="Trend confirmed with ATR expansion"
        )
    
        
    
    def _check_exit_conditions(self, regime, efficiency, close_price, atr) -> Optional[TradingSignal]:
        """
        Refactored Exit Logic: Uses Trailing Stops and removes Regime-flipping exits.
        """
        self.bar_count += 1
    
    # Track peak for trailing
        if close_price > self.highest_price:
            self.highest_price = close_price

    # A. SURVIVAL RULE: The "3-Hour Momentum" Check
    # If we are 3 candles in and not in profit, the trend is likely a fakeout.
        if self.bar_count >= 12 and close_price <= self.entry_price:
            return TradingSignal(SignalType.EXIT, 1.0, close_price, reason="Survival: No momentum")

    # B. DYNAMIC TRAILING: Chandelier Exit (2.5x ATR)
    # This gives the trade room to move while protecting the downside.
        trail_stop = self.highest_price - (atr * 2.5)
        if trail_stop > self.stop_loss:
            self.stop_loss = trail_stop

    # C. REGIME PROTECTION: Exit if market becomes 'Chaos' or 'Range'
        if regime in ['chaos', 'range']:
            return TradingSignal(SignalType.EXIT, 1.0, close_price, reason=f"Regime Shift: {regime}")

    # D. FINAL TRIGGER: Stop Hit
        if close_price <= self.stop_loss:
            return TradingSignal(SignalType.EXIT, 1.0, close_price, reason=f"Stop Hit @ {self.stop_loss:.2f}")

        return TradingSignal(SignalType.NO_TRADE, 0.0, close_price, reason="Trend Active")
    

    def _calculate_stop_loss(self, entry_price: float, atr: float) -> float:
        """
        Calculate stop loss price based on ATR while respecting Config limits.
        """
        from config.system_config import RISK_LIMITS
    
        if atr == 0 or np.isnan(atr) or atr is None:
        # Fallback: Use a distance that corresponds to our MAX_POSITION_SIZE
        # If we risk 1% and our max size is 50%, our stop must be at least 2% away.
        # Calculation: Risk% / MaxSize% = 0.01 / 0.50 = 0.02 (2%)
            fallback_pct = RISK_LIMITS.MAX_RISK_PER_TRADE / RISK_LIMITS.MAX_POSITION_SIZE_PERCENT
            return entry_price * (1 - fallback_pct)

        stop_distance = atr * self.stop_loss_atr_multiple
        stop_loss = entry_price - stop_distance
        
        # Keep the max_stop_price check (prevents position size errors)
        min_dist_pct = RISK_LIMITS.MAX_RISK_PER_TRADE / RISK_LIMITS.MAX_POSITION_SIZE_PERCENT
        max_stop_price = entry_price * (1 - min_dist_pct)
        
        # REMOVE the 0.95 (5%) floor. Let the ATR do its job.
        final_stop = min(max_stop_price, stop_loss)
        
        return float(final_stop)
    
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
        eff_range = 1.0 - self.entry_efficiency_threshold
        eff_confidence = (efficiency - self.entry_efficiency_threshold) / eff_range * 0.4 + 0.6
        
        # Adjust for regime confidence
        confidence = eff_confidence * regime_confidence
        
        # Boost for high volume
        if volume_regime == 'high' or volume_regime == 'very_high':
            confidence = min(1.0, confidence * 1.1)
        
        final_conf = eff_confidence * regime_confidence
        return max(0.60, final_conf)
    
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
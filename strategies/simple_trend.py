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
        entry_efficiency_threshold: float = 0.20,
        exit_efficiency_threshold: float = 0.05,
        min_regime_confidence: float = 0.70,
        stop_loss_atr_multiple: float = 4.5,  # This is our primary variable
        exit_patience: int = 20,
        take_profit_multiplier: float = 6.0,
        atr_period: int = 14,
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
        self.stop_loss_atr_multiple = stop_loss_atr_multiple
        
        # Secondary Parameters
        self.exit_efficiency_threshold = exit_efficiency_threshold
        self.min_regime_confidence = min_regime_confidence
        self.exit_patience = exit_patience
        self.take_profit_multiplier = take_profit_multiplier
        self.atr_period = atr_period
        
        # State Tracking
        self.entry_price = 0.0
        self.highest_price = 0.0 
        self.stop_loss = 0.0 
        self.bar_count = 0
        self.active_stop = 0.0
        self.name = "SimpleTrendStrategy"
        
        self.logger.info(
            f"SimpleTrendStrategy initialized: eff={entry_efficiency_threshold}, stop_mult={stop_loss_atr_multiple}"
        )
    
    def generate_signal(self, dataframe: pd.DataFrame, current_position: Optional[str] = None, current_capital: float = 500.0) -> TradingSignal:
        if len(dataframe) < 30:
            return TradingSignal(SignalType.NO_TRADE, 0.0, dataframe.iloc[-1]['close'], reason="Waiting for data")

        current_row = dataframe.iloc[-1]
        close_price = float(current_row['close'])
        atr = float(current_row.get('atr', 0))
        regime = str(current_row.get('regime', 'none')).lower()
        efficiency = float(current_row.get('efficiency_ratio', 0))
        regime_conf = float(current_row.get('regime_confidence', 0))

    # --- 1. EXIT LOGIC ---
        if current_position is not None:
            if self.highest_price == 0 or close_price > self.highest_price:
                self.highest_price = close_price
        
            # 1. Calculate the Trailing Stop
            trail_stop = self.highest_price - (atr * self.stop_loss_atr_multiple)
    
    # 2. BUFFER FIX: Ensure we only 'lock in' a stop that covers costs
    # Total estimated cost (0.075% fee + 0.1% slip) * 2 = 0.35%
            breakeven_price = self.entry_price * 1.004 
    
    # If we are in profit, try to keep the stop above breakeven
            if close_price > breakeven_price:
                self.active_stop = max(self.active_stop, trail_stop, breakeven_price)
            else:
                self.active_stop = max(self.active_stop, trail_stop)

            should_exit, reason = self._check_exit_conditions(regime, efficiency, close_price, self.active_stop)
        
            if should_exit:
                self.highest_price = 0 
                self.active_stop = 0
                return TradingSignal(
                signal_type=SignalType.EXIT, 
                confidence=1.0, 
                entry_price=close_price, 
                regime=regime, 
                reason=reason
            )
        
            return TradingSignal(SignalType.NO_TRADE, 0.0, close_price, reason="Holding Trend")

    # --- 2. INTEGRATED ENTRY LOGIC ---
    # Primary Gates
        is_trending = (regime == 'trend')
        is_efficient = (efficiency >= self.entry_efficiency_threshold)
        is_confident = (regime_conf >= self.min_regime_confidence)

        if is_trending and (efficiency >= 0.30 or is_confident):
            stop_price = close_price - (atr * self.stop_loss_atr_multiple)
            stop_dist_pct = abs(close_price - stop_price) / close_price
        
        # Prevent division by zero or nonsensical tight stops
            if stop_dist_pct < 0.002: stop_dist_pct = 0.002 

        # ADAPTIVE SIZING MATH: Size = Risk_Amount / Distance_to_Stop
            target_risk_amount = current_capital * 0.01  # Risk exactly 1% of total bankroll
            requested_rand_size = target_risk_amount / stop_dist_pct
        
        # Survival Cap: Never use more than 95% of capital even if stop is tight
            final_rand_size = min(requested_rand_size, current_capital * 0.95)
        
        # State Tracking for the trailing stop
            self.highest_price = close_price
            self.active_stop = stop_price
        
            return TradingSignal(
            signal_type=SignalType.LONG,
            confidence=1.0,
            entry_price=close_price,
            stop_loss=stop_price,
            size=final_rand_size,
            regime=regime,
            reason=f"Entry | R{final_rand_size:.2f} | Risk: 1% (Dist: {stop_dist_pct*100:.1f}%)"
        )

        return TradingSignal(SignalType.NO_TRADE, 0.0, close_price, reason=f"Wait: {regime}")
    
    
    
        
    
    def _check_exit_conditions(self, regime, efficiency, close_price, active_stop):
        """
        Check if we should jump out of the trade.
        """
        # 1. Trailing Stop Hit (The most important exit)
        if close_price <= active_stop:
            return True, "Stop Loss Hit"

    # SOFT EXIT: Only exit if the trend is fundamentally broken
    # We ignore 'chaos' or 'range' regimes once we are already in a trade.
        if efficiency < 0.10: 
            return True, "Efficiency Collapse"

        return False, None
    

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
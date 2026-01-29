import pandas as pd
import numpy as np
import logging
from .base import Strategy, SignalType, TradingSignal

class MeanReversionStrategy(Strategy):
    def __init__(self, window: int = 20, std_dev: float = 2.0):
        super().__init__()
        self.window = window
        self.std_dev = std_dev

    def get_name(self) -> str:
        return f"Mean Reversion (w={self.window}, std={self.std_dev})"

    def is_regime_compatible(self, regime: str) -> bool:
        # This strategy is designed to thrive in non-trending markets
        return regime in ['range', 'chaos']

    def generate_signal(self, data: pd.DataFrame, current_position: str = None) -> TradingSignal:
        self.validate_data(data)
        
        # Calculate Bollinger Bands on the fly
        closes = data['close']
        sma = closes.rolling(window=self.window).mean()
        std = closes.rolling(window=self.window).std()
        lower_band = sma - (self.std_dev * std)
        upper_band = sma + (self.std_dev * std)
        
        latest = data.iloc[-1]
        regime = latest['regime']
        
        # Default: Stay out
        sig_type = SignalType.NO_TRADE
        reason = "Wait for extremes"
        
        # Check Entry: Price below lower band + compatible regime
        if current_position is None:
            if latest['close'] < lower_band.iloc[-1] and self.is_regime_compatible(regime):
                sig_type = SignalType.LONG
                reason = "Price oversold in range/chaos"
        
        # Check Exit: Price returns to mean (SMA) or upper band
        elif current_position == 'long':
            if latest['close'] >= sma.iloc[-1]:
                sig_type = SignalType.EXIT
                reason = "Price returned to mean"

        signal = TradingSignal(
            signal_type=sig_type,
            confidence=0.8,
            entry_price=latest['close'],
            stop_loss=latest['close'] * 0.95, # 5% emergency stop
            regime=regime,
            reason=reason
        )
        
        self.record_signal(signal)
        return signal
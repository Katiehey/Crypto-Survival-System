from .base import Strategy, TradingSignal, SignalType
from .simple_trend import SimpleTrendStrategy
from .mean_reversion import MeanReversionStrategy
import pandas as pd
from typing import Optional

class MultiRegimeOrchestrator(Strategy):
    def __init__(self):
        super().__init__()
        self.trend_strat = SimpleTrendStrategy()
        self.reversion_strat = MeanReversionStrategy(window=36, std_dev=2.0)

    def get_name(self) -> str:
        return "Multi-Regime Orchestrator"

    def is_regime_compatible(self, regime: str) -> bool:
        return True  # The orchestrator handles all regimes

    def generate_signal(self, data: pd.DataFrame, current_position: str = None) -> TradingSignal:
        self.validate_data(data)
        regime = data.iloc[-1]['regime']
        signal = self.reversion_strat.generate_signal(data, current_position)
        signal.metadata['regime'] = regime
        
        # 🧠 DECISION LOGIC
        if regime == 'trend':
            # Use the trend-following logic for bull/bear runs
            signal = self.trend_strat.generate_signal(data, current_position)
            signal.reason = f"Trend Mode: {signal.reason}"
        elif regime == 'range':
            signal = self.reversion_strat.generate_signal(data, current_position)
            signal.reason = f"⚖️ Range Reversion: {signal.reason}"
        
        elif regime == 'chaos':
        # Defensive Mode: Use reversion logic but with a 50% size reduction
            signal = self.reversion_strat.generate_signal(data, current_position)
            signal.confidence *= 0.5 
            signal.reason = f"⚠️ Chaos Defense: {signal.reason}"
        else:
            # Stay safe in 'no_trade' regimes
            latest = data.iloc[-1]
            signal = TradingSignal(
                signal_type=SignalType.NO_TRADE,
                confidence=1.0,
                entry_price=latest['close'],
                regime=regime,
                reason="System-wide Pause: Uncertain Regime"
            )
        
        return signal
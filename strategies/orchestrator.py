from .base import Strategy, TradingSignal, SignalType
from .simple_trend import SimpleTrendStrategy
from .mean_reversion import MeanReversionStrategy
import pandas as pd
from typing import Optional

# Optional ML inference (loaded dynamically to avoid hard dependency)
try:
    from paper_trading.ml_inference import MLInference
except Exception:
    MLInference = None

class MultiRegimeOrchestrator(Strategy):
    def __init__(self, use_ml: bool = False, ml_model_path: str | None = None, ml_threshold: float = 0.6):
        super().__init__()
        # Tuned parameters to reduce micro-trades on small starting capital
        # Use conservative parameters chosen via walk-forward tuning
        self.trend_strat = SimpleTrendStrategy(
            entry_efficiency_threshold=0.60,
            exit_efficiency_threshold=0.40,
            stop_loss_atr_multiple=3.0,
            min_trade_value=50.0,
        )
        # Make mean-reversion slightly more conservative
        self.reversion_strat = MeanReversionStrategy(window=36, std_dev=2.5)

        # ML integration
        self.use_ml = use_ml and MLInference is not None
        self.ml = None
        if self.use_ml and ml_model_path:
            try:
                self.ml = MLInference(ml_model_path)
            except Exception as e:
                # If model is gated or fails to load, disable ML gracefully
                import logging
                logging.getLogger(__name__).warning(f"ML model not loaded: {e}. ML gating disabled.")
                self.ml = None
                self.use_ml = False
        self.ml_threshold = ml_threshold

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
            # ML gating: if enabled, require ML score to agree
            if self.ml is not None:
                score = self.ml.predict_score(data.iloc[-1:])
                if score < self.ml_threshold:
                    # downgrade to NO_TRADE
                    latest = data.iloc[-1]
                    return TradingSignal(
                        signal_type=SignalType.NO_TRADE,
                        confidence=1.0,
                        entry_price=latest['close'],
                        regime=regime,
                        reason=f"ML Reject (score={score:.2f})"
                    )
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
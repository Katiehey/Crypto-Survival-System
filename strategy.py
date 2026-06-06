"""
strategy.py — Adaptive market regime detection + trading logic.

Primary regime detection: HMM (5-state Gaussian Hidden Markov Model).
Fallback:                  ADX threshold when HMM confidence is low or model not trained.

HMM regimes and their strategy mapping:
  crash    → "ranging"  + entry BLOCKED  (no new entries, force exit longs)
  bear     → "ranging"  + entry BLOCKED  (no new entries, force exit longs)
  neutral  → "ranging"  (Bollinger Band mean reversion)
  bull     → "trending" (EMA + MACD trend following)
  euphoria → "trending" + 50% size reduction (parabolic — trail stops aggressively)

ADX fallback (when HMM confidence < HMM_MIN_CONFIDENCE or model not loaded):
  ADX > threshold  → "trending"
  ADX ≤ threshold  → "ranging"
"""

import logging
import pandas as pd

import config

logger = logging.getLogger(__name__)

# Lazy-load HMM — if hmmlearn not installed, silently degrade to ADX-only
_hmm_module = None
def _get_hmm_module():
    global _hmm_module
    if _hmm_module is None:
        try:
            import hmm_engine
            _hmm_module = hmm_engine
        except Exception:
            pass
    return _hmm_module


class RegimeDetector:
    """
    Detects market regime using HMM (primary) with ADX fallback.

    Returns a dict with both the strategy-mapped regime string ("trending" /
    "ranging") used by TechnicalAgent, and the raw HMM regime + confidence for
    use by bot.py to handle crash / bear / euphoria edge cases.
    """

    def __init__(self, period: int = 14, threshold: float = None):
        self.period    = period
        self.threshold = threshold or config.ADX_TREND_THRESHOLD
        self._hmm      = None

        if config.HMM_ENABLED:
            mod = _get_hmm_module()
            if mod is not None:
                self._hmm = mod.HMMRegimeDetector(config.HMM_MODEL_PATH)
                loaded = self._hmm.load_model()
                if not loaded:
                    logger.info("HMM model not found — using ADX regime detection until trained")

    def detect(self, df: pd.DataFrame) -> dict:
        """
        Returns:
            regime:          "trending" | "ranging" (strategy path for TechnicalAgent)
            adx:             float (always computed for diagnostics)
            plus_di:         float
            minus_di:        float
            direction:       "up" | "down" | "unclear"
            hmm_regime:      str | None  (crash/bear/neutral/bull/euphoria)
            hmm_confidence:  float       (0.0 if HMM not used)
            hmm_probs:       dict        (all 5 posterior probabilities)
            hmm_fallback:    bool        (True = ADX was used instead of HMM)
        """
        try:
            adx, plus_di, minus_di = self._compute_adx(df, self.period)
            last_adx      = adx.iloc[-1]
            last_plus_di  = plus_di.iloc[-1]
            last_minus_di = minus_di.iloc[-1]

            # ADX regime — used as fallback and always logged for diagnostics
            recent_adx = adx.iloc[-3:]
            if all(a > self.threshold for a in recent_adx):
                adx_regime = "trending"
            elif all(a <= self.threshold for a in recent_adx):
                adx_regime = "ranging"
            else:
                adx_regime = "ranging"   # transitioning — stay conservative

            direction = ("up" if last_plus_di > last_minus_di else "down") if adx_regime == "trending" else "unclear"

            base = {
                "adx":      round(last_adx, 2),
                "plus_di":  round(last_plus_di, 2),
                "minus_di": round(last_minus_di, 2),
                "direction": direction,
            }

            # ── Try HMM first ─────────────────────────────────────────────────
            if self._hmm is not None and self._hmm.is_ready():
                hmm_regime, hmm_conf = self._hmm.predict_regime(df)
                hmm_probs            = self._hmm.get_regime_probabilities(df)

                if hmm_conf >= config.HMM_MIN_CONFIDENCE:
                    mod = _get_hmm_module()
                    strategy_regime = mod.REGIME_TO_STRATEGY[hmm_regime]
                    logger.debug(
                        f"HMM regime={hmm_regime} conf={hmm_conf:.2f} "
                        f"→ strategy={strategy_regime}"
                    )
                    return {
                        **base,
                        "regime":         strategy_regime,
                        "hmm_regime":     hmm_regime,
                        "hmm_confidence": hmm_conf,
                        "hmm_probs":      hmm_probs,
                        "hmm_fallback":   False,
                    }
                else:
                    logger.debug(
                        f"HMM confidence too low ({hmm_conf:.2f} < {config.HMM_MIN_CONFIDENCE}) "
                        f"— falling back to ADX"
                    )

            # ── ADX fallback ──────────────────────────────────────────────────
            logger.debug(
                f"ADX regime: {adx_regime} "
                f"(ADX={last_adx:.1f}, +DI={last_plus_di:.1f}, -DI={last_minus_di:.1f})"
            )
            return {
                **base,
                "regime":         adx_regime,
                "hmm_regime":     None,
                "hmm_confidence": 0.0,
                "hmm_probs":      {},
                "hmm_fallback":   True,
            }

        except Exception as e:
            logger.warning(f"RegimeDetector error: {e}")
            return {
                "regime": "ranging", "adx": 0, "plus_di": 0, "minus_di": 0,
                "direction": "unclear", "hmm_regime": None,
                "hmm_confidence": 0.0, "hmm_probs": {}, "hmm_fallback": True,
            }

    @staticmethod
    def _compute_adx(df: pd.DataFrame, period: int = 14):
        """Pure pandas ADX calculation."""
        high  = df["high"]
        low   = df["low"]
        close = df["close"]

        prev_high  = high.shift(1)
        prev_low   = low.shift(1)
        prev_close = close.shift(1)

        # True Range
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low  - prev_close).abs(),
        ], axis=1).max(axis=1)

        # Directional movement
        up_move   = high - prev_high
        down_move = prev_low - low

        plus_dm  = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        # Wilder smoothing
        atr      = tr.ewm(alpha=1 / period, adjust=False).mean()
        plus_di  = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, 1e-10)
        minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, 1e-10)

        dx  = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10)
        adx = dx.ewm(alpha=1 / period, adjust=False).mean()

        return adx, plus_di, minus_di


class TradingStrategy:
    """
    Calculates dynamic stop-loss and take-profit levels based on ATR.
    Also handles grid level calculation for ranging markets.
    """

    def __init__(self):
        self.regime_detector = RegimeDetector()

    def compute_levels(
        self,
        df: pd.DataFrame,
        signal: str,
        regime: str,
    ) -> dict:
        """
        Returns entry, stop_loss, take_profit, and position_size in USDT.
        """
        close = df["close"].iloc[-1]
        atr   = self._atr(df, 14).iloc[-1]

        if signal == "BUY":
            entry      = close
            stop_loss  = entry - config.ATR_STOP_MULT   * atr
            take_profit = entry + config.ATR_TARGET_MULT * atr
        elif signal == "SELL":
            entry      = close
            stop_loss  = entry + config.ATR_STOP_MULT   * atr
            take_profit = entry - config.ATR_TARGET_MULT * atr
        else:
            return {}

        risk_reward = abs(take_profit - entry) / abs(stop_loss - entry)

        return {
            "entry":       round(entry, 2),
            "stop_loss":   round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "atr":         round(atr, 2),
            "risk_reward": round(risk_reward, 2),
            "regime":      regime,
        }

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high, low, close = df["high"], df["low"], df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low  - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()

"""
strategy.py — Adaptive market regime detection + trading logic.

Regime detection uses ADX:
  ADX > 25  → "trending"  → trend-following (EMA crossover + RSI)
  ADX ≤ 25  → "ranging"   → mean-reversion  (Bollinger + RSI)
"""

import logging
import pandas as pd

import config

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Detects whether the market is trending or ranging using ADX(14).
    Also returns raw ADX value and +DI/-DI for diagnostics.
    """

    def __init__(self, period: int = 14, threshold: float = None):
        self.period    = period
        self.threshold = threshold or config.ADX_TREND_THRESHOLD

    def detect(self, df: pd.DataFrame) -> dict:
        """
        Returns:
            regime: "trending" | "ranging"
            adx: float
            plus_di: float
            minus_di: float
            direction: "up" | "down" | "unclear" (only meaningful in trending regime)
        """
        try:
            adx, plus_di, minus_di = self._compute_adx(df, self.period)
            last_adx      = adx.iloc[-1]
            last_plus_di  = plus_di.iloc[-1]
            last_minus_di = minus_di.iloc[-1]

            # Require 3 consecutive bars above/below threshold before flipping
            # regime — prevents whipsawing when ADX hovers near the boundary.
            recent_adx = adx.iloc[-3:]
            if all(a > self.threshold for a in recent_adx):
                regime = "trending"
            elif all(a <= self.threshold for a in recent_adx):
                regime = "ranging"
            else:
                regime = "ranging"  # transitioning — stay conservative

            if regime == "trending":
                direction = "up" if last_plus_di > last_minus_di else "down"
            else:
                direction = "unclear"

            result = {
                "regime":    regime,
                "adx":       round(last_adx, 2),
                "plus_di":   round(last_plus_di, 2),
                "minus_di":  round(last_minus_di, 2),
                "direction": direction,
            }
            logger.debug(
                f"Regime: {regime} (ADX={last_adx:.1f}, +DI={last_plus_di:.1f}, -DI={last_minus_di:.1f})"
            )
            return result

        except Exception as e:
            logger.warning(f"RegimeDetector error: {e}")
            return {"regime": "ranging", "adx": 0, "plus_di": 0, "minus_di": 0, "direction": "unclear"}

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

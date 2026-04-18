"""
ml_filter.py — ML-based signal quality filter.

Trains a logistic regression on historical backtest trade outcomes.
At inference, filters out signals with low predicted win probability.

Training flow:
    python bot.py --train-filter   # runs backtest, extracts features, trains model

Inference: loaded automatically by ConsensusEngine when ops/signal_filter.pkl exists.
If no model is trained yet, filter is transparent (all signals pass through).
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_PATH = Path("ops/signal_filter.pkl")
MIN_TRADES_TO_TRAIN = 20  # minimum historical trades needed

# Feature order must never change once a model is trained
FEATURE_ORDER = [
    "rsi",
    "atr_pct",
    "macd_hist",
    "ema20_dist",
    "ema50_dist",
    "ema200_dist",
    "vol_ratio",
    "adx",
    "is_buy",
]


def extract_features(df: pd.DataFrame, signal: str) -> dict:
    """
    Extract ML features from a window of OHLCV data at entry time.
    Must be called identically in both backtest (training) and live bot (inference).

    df: window of OHLCV bars ending at the entry candle
    signal: "BUY" or "SELL"
    """
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    # ── RSI(14) ────────────────────────────────────────────────────────────────
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, 1e-10)
    rsi   = float((100 - (100 / (1 + rs))).iloc[-1])

    # ── ATR % of price ────────────────────────────────────────────────────────
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr     = float(tr.rolling(14).mean().iloc[-1])
    atr_pct = atr / float(close.iloc[-1])

    # ── MACD histogram ────────────────────────────────────────────────────────
    ema_fast    = close.ewm(span=12, adjust=False).mean()
    ema_slow    = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist   = float((macd_line - signal_line).iloc[-1])

    # ── EMA distances (% from price) ──────────────────────────────────────────
    ema20  = close.ewm(span=20,  adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    lc = float(close.iloc[-1])
    ema20_dist  = (lc - float(ema20.iloc[-1]))  / lc
    ema50_dist  = (lc - float(ema50.iloc[-1]))  / lc
    ema200_dist = (lc - float(ema200.iloc[-1])) / lc

    # ── Volume ratio (current vs 20-bar avg) ──────────────────────────────────
    vol_avg   = float(df["volume"].rolling(20).mean().iloc[-1])
    vol_ratio = float(df["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0

    # ── ADX(14) ───────────────────────────────────────────────────────────────
    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm   = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm  = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr_14    = tr.rolling(14).mean()
    plus_di   = 100 * (plus_dm.rolling(14).mean() / atr_14.replace(0, 1e-10))
    minus_di  = 100 * (minus_dm.rolling(14).mean() / atr_14.replace(0, 1e-10))
    dx        = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10)
    adx       = float(dx.rolling(14).mean().iloc[-1])

    return {
        "rsi":        rsi,
        "atr_pct":    atr_pct,
        "macd_hist":  macd_hist,
        "ema20_dist": ema20_dist,
        "ema50_dist": ema50_dist,
        "ema200_dist": ema200_dist,
        "vol_ratio":  vol_ratio,
        "adx":        adx,
        "is_buy":     1.0 if signal == "BUY" else 0.0,
    }


def features_to_array(features: dict) -> np.ndarray:
    """Convert a feature dict to a numpy array in the canonical feature order."""
    return np.array([features[k] for k in FEATURE_ORDER], dtype=float)


class SignalFilter:
    """
    Logistic regression filter trained on historical backtest trade outcomes.

    - sklearn is only required for training (--train-filter).
    - Inference uses stored weights/bias — no sklearn dependency at runtime.
    - When no model exists yet, predict() is a transparent passthrough.
    """

    THRESHOLD = 0.55  # require >55% predicted win probability

    def __init__(self):
        self._model: dict | None = None
        self._load()

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def _load(self):
        if MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    self._model = pickle.load(f)
                logger.info(
                    f"ML filter loaded — "
                    f"n={self._model.get('n_samples', '?')} trades, "
                    f"base_win_rate={self._model.get('win_rate', 0):.1%}"
                )
            except Exception as e:
                logger.warning(f"ML filter load failed: {e}")
                self._model = None

    def predict(self, features: dict) -> tuple[bool, float]:
        """
        Returns (should_trade, win_probability).
        If no model trained yet: returns (True, 0.5) — transparent passthrough.
        On any error: returns (True, 0.5) — fail-open, never blocks trading.
        """
        if not self.is_trained:
            return True, 0.5
        try:
            x = features_to_array(features).reshape(1, -1)
            x_norm = (x - self._model["mean"]) / (self._model["std"] + 1e-10)
            logit  = float(
                np.dot(x_norm, self._model["weights"]) + self._model["bias"]
            )
            prob = float(1.0 / (1.0 + np.exp(-logit)))
            return prob >= self.THRESHOLD, round(prob, 3)
        except Exception as e:
            logger.warning(f"ML filter predict error: {e}")
            return True, 0.5

    def train(self, features_list: list[dict], outcomes: list[int]) -> bool:
        """
        Train on a list of feature dicts and binary outcomes (1=win, 0=loss).
        Saves model to ops/signal_filter.pkl. Returns True on success.

        Requires scikit-learn (pip install scikit-learn).
        """
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import cross_val_score
        except ImportError:
            logger.error("scikit-learn not installed — run: pip install scikit-learn")
            return False

        n = len(features_list)
        if n < MIN_TRADES_TO_TRAIN:
            logger.warning(
                f"Only {n} trades — need {MIN_TRADES_TO_TRAIN} to train the filter. "
                f"Run a longer backtest (try --backtest-days 600) first."
            )
            return False

        X = np.array([features_to_array(f) for f in features_list])
        y = np.array(outcomes, dtype=int)

        scaler = StandardScaler()
        X_sc   = scaler.fit_transform(X)

        # C=0.5 gives mild L2 regularisation — avoids overfitting on small datasets
        clf = LogisticRegression(C=0.5, max_iter=1000, random_state=42)

        if n >= 30:
            folds = min(5, n // 6)
            cv = cross_val_score(clf, X_sc, y, cv=folds, scoring="accuracy")
            logger.info(
                f"ML filter cross-val accuracy: {cv.mean():.1%} ± {cv.std():.1%} "
                f"({folds}-fold)"
            )

        clf.fit(X_sc, y)

        # Store as pure numpy so inference needs no sklearn
        model_data = {
            "mean":      scaler.mean_,
            "std":       scaler.scale_,
            "weights":   clf.coef_[0],
            "bias":      clf.intercept_[0],
            "n_samples": n,
            "win_rate":  float(y.mean()),
        }

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model_data, f)

        self._model = model_data
        logger.info(
            f"ML filter trained: {n} samples, "
            f"win_rate={y.mean():.1%} — saved to {MODEL_PATH}"
        )
        return True

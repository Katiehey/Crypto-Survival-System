"""
hmm_engine.py — Probabilistic market regime detection using a Hidden Markov Model.

Why HMM over ADX:
  ADX is a 14-period Wilder-smoothed indicator — it can take 10+ bars to confirm
  a regime change because the smoothing deliberately lags. HMM treats regime as a
  hidden state that probabilistically generates observable features; transition
  probabilities are learned from data, so regime changes are detected earlier with
  an explicit confidence score rather than a binary threshold.

5 hidden states, sorted by learned mean log-return after fitting:
  crash    — high volatility, strongly negative returns (severe sell-off)
  bear     — moderate negative returns (grinding downtrend)
  neutral  — near-zero returns, low volatility (sideways/ranging)
  bull     — moderate positive returns (steady uptrend)
  euphoria — high volatility, strongly positive returns (parabolic move)

Features derived from 1h OHLCV (no external data needed):
  log_return   : per-bar directional bias — primary regime separator
  volatility   : 20-bar rolling std of log returns — vol regime clustering
  volume_ratio : bar vol / 50-bar average — liquidity and conviction
  atr_ratio    : ATR(14) / price — normalised intraday range
  ema_spread   : (EMA20 − EMA50) / price — trend strength and direction

How confidence scores work:
  After fitting, hmmlearn can compute posterior state probabilities given the
  full observed feature sequence via the forward-backward algorithm. The
  confidence returned is the posterior probability of the predicted state for
  the most recent bar. A value of 0.9 means the model is 90% certain the
  current regime is X; below HMM_MIN_CONFIDENCE (default 0.6) fall back to ADX.

When to retrain:
  Retrain every HMM_RETRAIN_DAYS (default 30) — BTC's vol/correlation structure
  shifts over months, so a model trained on a different regime can mislabel.
  The --train-hmm CLI flag triggers a fresh 730-day training run.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from hmmlearn.hmm import GaussianHMM
    from sklearn.preprocessing import StandardScaler
    import joblib
    _HMM_AVAILABLE = True
except ImportError:
    _HMM_AVAILABLE = False
    logger.warning(
        "hmmlearn not installed — HMM regime detection unavailable. "
        "Install: pip install hmmlearn joblib"
    )


# Regime names ordered from most negative to most positive mean log-return
REGIME_NAMES = ["crash", "bear", "neutral", "bull", "euphoria"]

# Colour palette — dark theme to match existing dashboard and charts
REGIME_COLORS = {
    "crash":    "#8b0000",   # dark red
    "bear":     "#cd5c5c",   # indian red
    "neutral":  "#4a5568",   # slate gray
    "bull":     "#2d6a4f",   # forest green
    "euphoria": "#f6c90e",   # gold
}

# Maps HMM regime to the strategy path string used by TechnicalAgent
# crash/bear both map to "ranging" — bot.py handles the entry block separately
REGIME_TO_STRATEGY = {
    "crash":    "ranging",
    "bear":     "ranging",
    "neutral":  "ranging",
    "bull":     "trending",
    "euphoria": "trending",
}

# Regimes where no new entries should be opened (handled in bot.py/_tick)
BLOCKED_REGIMES = frozenset({"crash", "bear"})


class HMMRegimeDetector:
    """
    5-state Gaussian HMM for market regime classification.

    Typical workflow:
        hmm = HMMRegimeDetector()
        ok  = hmm.load_model()          # try to load from disk first
        if not ok:
            df  = fetch_historical(...)  # 730 days of 1h OHLCV
            hmm.fit(df)
            hmm.save_model()

        regime, conf = hmm.predict_regime(live_df)
    """

    N_STATES    = 5
    N_ITER      = 200    # EM iterations — convergence typically < 100, 200 is safe margin
    RANDOM_SEED = 42     # fixed seed → reproducible state ordering across runs

    def __init__(self, model_path: str = "ops/hmm_model.pkl"):
        self.model_path           = model_path
        self.model:  Optional[GaussianHMM]    = None
        self.scaler: Optional[StandardScaler] = None
        self._state_to_regime: dict[int, str] = {}
        self._train_time: Optional[datetime]  = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def fit(self, df: pd.DataFrame) -> bool:
        """
        Train the HMM on historical OHLCV data. Returns True on success.

        After EM converges, states are sorted by mean log-return so the label
        mapping (crash…euphoria) is stable across retraining runs regardless of
        the arbitrary ordering hmmlearn uses internally.

        Minimum recommended input: 5 000 bars (~7 months of 1h data).
        """
        if not _HMM_AVAILABLE:
            logger.error("hmmlearn not installed — cannot train HMM")
            return False
        try:
            features = self._extract_features(df)
            if features is None or len(features) < self.N_STATES * 100:
                logger.error(
                    f"Insufficient data for HMM training "
                    f"({0 if features is None else len(features)} bars, "
                    f"need ≥ {self.N_STATES * 100})"
                )
                return False

            # Standardise: HMM emission likelihoods are sensitive to feature scale
            self.scaler = StandardScaler()
            X = self.scaler.fit_transform(features)

            logger.info(f"Fitting HMM on {len(X)} bars …")
            self.model = GaussianHMM(
                n_components=self.N_STATES,
                covariance_type="diag",   # diagonal covariance: regularised + stable
                n_iter=self.N_ITER,
                random_state=self.RANDOM_SEED,
                verbose=False,
            )
            self.model.fit(X)

            # Sort states by mean log-return (feature index 0) → crash…euphoria
            means_orig  = self.scaler.inverse_transform(self.model.means_)
            sorted_idx  = np.argsort(means_orig[:, 0])   # ascending
            self._state_to_regime = {
                int(state): REGIME_NAMES[rank]
                for rank, state in enumerate(sorted_idx)
            }

            self._train_time = datetime.now(timezone.utc)
            summary = ", ".join(
                f"{self._state_to_regime[i]}={means_orig[i, 0]:.5f}"
                for i in range(self.N_STATES)
            )
            logger.info(f"HMM trained — mean log-returns by state: {summary}")
            return True

        except Exception as e:
            logger.error(f"HMM training failed: {e}", exc_info=True)
            return False

    def predict_regime(self, df: pd.DataFrame) -> tuple[str, float]:
        """
        Return (regime_name, confidence) for the most recent bar.

        Confidence = posterior probability of the predicted state given the last
        ≤500 bars of features. Below HMM_MIN_CONFIDENCE the caller should fall
        back to ADX-based detection.
        """
        probs = self.get_regime_probabilities(df)
        if not probs:
            return "neutral", 0.0
        best = max(probs, key=probs.get)
        return best, round(probs[best], 3)

    def get_regime_probabilities(self, df: pd.DataFrame) -> dict[str, float]:
        """
        Return {regime_name: posterior_probability} for the current bar.
        All probabilities sum to 1.0. Returns {} on any failure.
        """
        if not self.is_ready():
            return {}
        try:
            features = self._extract_features(df)
            if features is None or len(features) < 10:
                return {}
            # 500-bar window: stable posteriors without being slow on live ticks
            X          = self.scaler.transform(features[-500:])
            posteriors = self.model.predict_proba(X)   # shape: (n_bars, n_states)
            last       = posteriors[-1]                 # most recent bar
            return {
                self._state_to_regime[i]: round(float(last[i]), 4)
                for i in range(self.N_STATES)
            }
        except Exception as e:
            logger.warning(f"HMM predict_proba failed: {e}")
            return {}

    def save_model(self, path: str = None) -> bool:
        """Persist model + scaler + state map to disk via joblib."""
        path = path or self.model_path
        if not self.is_ready():
            logger.warning("Nothing to save — model not trained yet")
            return False
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            joblib.dump({
                "model":           self.model,
                "scaler":          self.scaler,
                "state_to_regime": self._state_to_regime,
                "train_time":      self._train_time,
            }, path)
            logger.info(f"HMM model saved → {path}")
            return True
        except Exception as e:
            logger.error(f"HMM save failed: {e}")
            return False

    def load_model(self, path: str = None) -> bool:
        """Load trained model from disk. Returns True on success."""
        path = path or self.model_path
        if not Path(path).exists():
            return False
        if not _HMM_AVAILABLE:
            logger.warning("hmmlearn not installed — cannot load HMM model")
            return False
        try:
            data = joblib.load(path)
            self.model            = data["model"]
            self.scaler           = data["scaler"]
            self._state_to_regime = data["state_to_regime"]
            self._train_time      = data.get("train_time")
            logger.info(
                f"HMM model loaded (trained {self.model_age_days():.0f}d ago, "
                f"states: {self._state_to_regime})"
            )
            return True
        except Exception as e:
            logger.error(f"HMM load failed: {e}")
            return False

    def is_ready(self) -> bool:
        """True if model is trained/loaded and ready for inference."""
        return (
            _HMM_AVAILABLE
            and self.model  is not None
            and self.scaler is not None
            and bool(self._state_to_regime)
        )

    def needs_retrain(self, retrain_days: int = 30) -> bool:
        """True if the model file is missing or older than retrain_days."""
        if not Path(self.model_path).exists():
            return True
        return self.model_age_days() > retrain_days

    def model_age_days(self) -> float:
        """Days since last training. Returns inf if train_time is unknown."""
        if self._train_time is None:
            return float("inf")
        return (datetime.now(timezone.utc) - self._train_time).total_seconds() / 86400

    def plot_regimes(
        self,
        df: pd.DataFrame,
        save_path: str = "ops/hmm_regimes.png",
        title: str = "HMM Regime Detection — BTC/USDT 1h",
    ):
        """
        Plot price as a line with coloured background shading per detected regime.
        Saves a PNG. Dark theme to match the existing dashboard aesthetic.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
        except ImportError:
            logger.error("matplotlib not installed — cannot plot")
            return

        if not self.is_ready():
            logger.error("Model not ready — call fit() or load_model() first")
            return

        features = self._extract_features(df)
        if features is None:
            logger.error("Feature extraction failed — cannot plot")
            return

        X       = self.scaler.transform(features)
        states  = self.model.predict(X)
        regimes = [self._state_to_regime[s] for s in states]
        plot_df = df.iloc[-len(features):].copy()

        plt.rcParams.update({
            "figure.facecolor":  "#0d1117",
            "axes.facecolor":    "#161b22",
            "axes.edgecolor":    "#30363d",
            "axes.labelcolor":   "#c9d1d9",
            "axes.titlecolor":   "#c9d1d9",
            "xtick.color":       "#8b949e",
            "ytick.color":       "#8b949e",
            "text.color":        "#c9d1d9",
            "grid.color":        "#21262d",
            "grid.linestyle":    "--",
            "grid.linewidth":    0.5,
            "font.family":       "monospace",
        })

        fig, ax = plt.subplots(figsize=(16, 6))
        fig.suptitle(
            f"{title}  "
            f"[{plot_df.index[0].strftime('%Y-%m-%d')} → "
            f"{plot_df.index[-1].strftime('%Y-%m-%d')}]",
            fontsize=12, fontweight="bold",
        )

        # Group consecutive identical regimes into background spans
        regime_arr = np.array(regimes)
        change_pts = np.where(np.concatenate([[True], regime_arr[1:] != regime_arr[:-1]]))[0]
        change_pts = np.append(change_pts, len(regime_arr))
        for start, end in zip(change_pts[:-1], change_pts[1:]):
            ax.axvspan(
                start, end - 1,
                alpha=0.22, color=REGIME_COLORS[regime_arr[start]], zorder=0,
            )

        # Price line
        ax.plot(
            list(range(len(plot_df))),
            plot_df["close"].values,
            color="#58a6ff", linewidth=1.1, zorder=2,
        )
        ax.set_ylabel("Price (USDT)")
        ax.set_xlabel("Bar (1h)")
        ax.grid(True, zorder=0)

        # Regime distribution in footer
        counts = Counter(regimes)
        total  = len(regimes)
        stats  = "  ".join(
            f"{r}: {counts.get(r, 0) / total * 100:.0f}%"
            for r in REGIME_NAMES
        )
        ax.text(
            0.01, 0.02, stats, transform=ax.transAxes,
            fontsize=8, color="#8b949e",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#161b22", alpha=0.8),
        )

        patches = [
            mpatches.Patch(color=REGIME_COLORS[r], alpha=0.65, label=r.capitalize())
            for r in REGIME_NAMES
        ]
        ax.legend(handles=patches, loc="upper right", fontsize=8,
                  framealpha=0.3, ncol=5)

        plt.tight_layout()
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close()
        logger.info(f"Regime chart saved → {save_path}")

    # ── Private helpers ────────────────────────────────────────────────────────

    def _extract_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """
        Build (n_bars × 5) feature matrix from OHLCV.
        Drops leading NaN rows from rolling windows.
        Returns None on failure or if fewer than 50 clean rows remain.

        Feature contributions:
          log_return   — separates crash/bear from bull/euphoria on mean
          volatility   — separates euphoria/crash (high vol) from neutral (low vol)
          volume_ratio — confirms regime with liquidity signal
          atr_ratio    — secondary vol signal, normalised for price level
          ema_spread   — encodes trend direction and magnitude
        """
        try:
            close  = df["close"]
            high   = df["high"]
            low    = df["low"]
            volume = df["volume"]

            log_ret    = np.log(close / close.shift(1))
            volatility = log_ret.rolling(20).std()
            vol_avg    = volume.rolling(50).mean()
            vol_ratio  = (volume / vol_avg.replace(0, np.nan)).clip(0, 5)

            prev_close = close.shift(1)
            tr = pd.concat([
                high - low,
                (high - prev_close).abs(),
                (low  - prev_close).abs(),
            ], axis=1).max(axis=1)
            atr_ratio = tr.rolling(14).mean() / close

            ema20      = close.ewm(span=20, adjust=False).mean()
            ema50      = close.ewm(span=50, adjust=False).mean()
            ema_spread = (ema20 - ema50) / close

            feat = pd.DataFrame({
                "log_return":   log_ret,
                "volatility":   volatility,
                "volume_ratio": vol_ratio,
                "atr_ratio":    atr_ratio,
                "ema_spread":   ema_spread,
            }).replace([np.inf, -np.inf], np.nan).dropna()

            return feat.values if len(feat) >= 50 else None

        except Exception as e:
            logger.warning(f"HMM feature extraction failed: {e}")
            return None

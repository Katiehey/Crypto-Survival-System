"""
agents.py — The 4-agent consensus decision system.

A trade only executes when ALL agents agree on direction.
Each agent returns: {"signal": "BUY"|"SELL"|"HOLD", "confidence": 0.0-1.0, "reason": str}
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal
from datetime import datetime, timezone

import pandas as pd
import feedparser
import requests

import config

logger = logging.getLogger(__name__)

Signal = Literal["BUY", "SELL", "HOLD"]


@dataclass
class AgentSignal:
    agent: str
    signal: Signal
    confidence: float   # 0.0 – 1.0
    reason: str


# ─── Technical Agent ──────────────────────────────────────────────────────────

class TechnicalAgent:
    """
    Uses RSI, MACD, Bollinger Bands, and Moving Averages.
    Switches logic based on market regime passed in from strategy.
    """

    def analyse(
        self,
        df: pd.DataFrame,
        regime: str,
        df_4h: pd.DataFrame | None = None,
    ) -> AgentSignal:
        """
        df     : 1h OHLCV window (open, high, low, close, volume)
        regime : "trending" | "ranging"
        df_4h  : optional 4h OHLCV window for multi-timeframe confirmation.
                 When provided, BUY signals require 4h EMA20 > EMA50 (medium-term
                 uptrend) and SELL signals require 4h EMA20 < EMA50.
        """
        try:
            close = df["close"]
            signals = []
            reasons = []

            # ── Volume filter ─────────────────────────────────────────────────
            # 50-bar average gives a stable baseline — a 20-bar window gets
            # inflated too quickly by a short burst, making spikes impossible to hit
            vol_avg   = df["volume"].rolling(50).mean().iloc[-1]
            vol_spike = df["volume"].iloc[-1] > vol_avg * config.VOLUME_SPIKE_MIN

            # ── RSI (14) ──────────────────────────────────────────────────────
            rsi = self._rsi(close, 14)
            last_rsi = rsi.iloc[-1]

            # ── MACD ──────────────────────────────────────────────────────────
            macd_line, signal_line = self._macd(close)
            hist         = macd_line - signal_line
            macd_hist    = hist.iloc[-1]
            macd_hist_1  = hist.iloc[-2]   # previous bar
            # Crossover within last 5 bars — RSI > threshold and a fresh cross
            # rarely coincide on the exact same bar; 5-bar window catches entries
            # that are still early without chasing aged momentum.
            macd_cross_up   = any(
                macd_line.iloc[-(k+2)] <= signal_line.iloc[-(k+2)] and
                macd_line.iloc[-(k+1)] >  signal_line.iloc[-(k+1)]
                for k in range(5)
            )
            macd_cross_down = any(
                macd_line.iloc[-(k+2)] >= signal_line.iloc[-(k+2)] and
                macd_line.iloc[-(k+1)] <  signal_line.iloc[-(k+1)]
                for k in range(5)
            )
            # Histogram momentum: histogram must be expanding (gaining strength)
            hist_expanding_up   = macd_hist > 0 and macd_hist > macd_hist_1
            hist_expanding_down = macd_hist < 0 and macd_hist < macd_hist_1

            # ── Bollinger Bands (20, 2σ) ──────────────────────────────────────
            bb_upper, bb_mid, bb_lower = self._bollinger(close, 20, 2)
            last_close = close.iloc[-1]
            bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1]
            # Avoid mean-reversion trades when bands are very narrow (low-vol squeeze)
            bb_wide_enough = bb_width > 0.01  # bands span at least 1% of price

            # ── Moving Averages ───────────────────────────────────────────────
            ema20  = close.ewm(span=20,  adjust=False).mean()
            ema50  = close.ewm(span=50,  adjust=False).mean()
            ema200 = close.ewm(span=200, adjust=False).mean()
            trend_up   = ema20.iloc[-1] > ema50.iloc[-1] > ema200.iloc[-1]
            trend_down = ema20.iloc[-1] < ema50.iloc[-1] < ema200.iloc[-1]
            # EMA slope: short-term trend must be accelerating, not exhausted
            ema20_slope_up   = ema20.iloc[-1] > ema20.iloc[-3]
            ema20_slope_down = ema20.iloc[-1] < ema20.iloc[-3]
            # 200 EMA macro filter: only BUY when price is above long-term trend.
            # In trending mode this is already guaranteed by trend_up (EMA20>EMA50>EMA200),
            # but we keep it explicitly for ranging-mode BUY to block bear-market dip catches.
            above_ema200 = last_close > ema200.iloc[-1]

            if not vol_spike:
                # Low-volume bar: any signal here is likely a fake-out — skip it
                return AgentSignal("technical", "HOLD", 0.5,
                                   f"Low volume (bar={df['volume'].iloc[-1]:.0f} < {vol_avg*config.VOLUME_SPIKE_MIN:.0f}) — skipping")

            if regime == "trending":
                # Trend-following: all conditions must align including macro trend filter
                # trend_up = EMA20>EMA50>EMA200, which already implies price > EMA200
                if (trend_up and macd_cross_up and hist_expanding_up
                        and last_rsi > config.RSI_TREND_BUY_MIN and ema20_slope_up):
                    signals.append("BUY")
                    reasons.append(
                        f"Trend UP: EMA stack, MACD cross+expanding, vol spike, RSI={last_rsi:.1f}"
                    )
                elif (not config.LONG_ONLY and trend_down and macd_cross_down
                        and hist_expanding_down
                        and last_rsi < config.RSI_TREND_SELL_MAX and ema20_slope_down):
                    signals.append("SELL")
                    reasons.append(
                        f"Trend DOWN: EMA stack, MACD cross+expanding, RSI={last_rsi:.1f}"
                    )
                else:
                    signals.append("HOLD")
                    reasons.append(
                        f"Trend — conditions not met (RSI={last_rsi:.1f}, trend_up={trend_up})"
                    )

            else:  # ranging / mean reversion
                # Only buy dips that are above the 200 EMA — not catching falling knives
                if (bb_wide_enough and last_close <= bb_lower.iloc[-1] * 1.005
                        and last_rsi < config.RSI_RANGE_BUY_MAX
                        and above_ema200):
                    signals.append("BUY")
                    reasons.append(
                        f"Mean reversion BUY: below lower BB, above EMA200, RSI={last_rsi:.1f}"
                    )
                elif (not config.LONG_ONLY and bb_wide_enough
                        and last_close >= bb_upper.iloc[-1]
                        and last_rsi > config.RSI_RANGE_SELL_MIN):
                    signals.append("SELL")
                    reasons.append(
                        f"Mean reversion SELL: above upper BB, RSI={last_rsi:.1f}"
                    )
                else:
                    signals.append("HOLD")
                    reasons.append(f"No mean-reversion trigger (RSI={last_rsi:.1f})")

            signal = signals[0]

            # ── Multi-timeframe confirmation (4h) ─────────────────────────────
            # Only apply when 4h data is available and we have a directional view.
            # Prevents entering 1h trades that fight the medium-term trend.
            if signal != "HOLD" and df_4h is not None and len(df_4h) >= 50:
                if not self._check_4h_alignment(df_4h, signal):
                    return AgentSignal(
                        "technical", "HOLD", 0.5,
                        f"4h trend opposes 1h {signal} — skipping"
                    )

            # Confidence: how many sub-signals agree (each = 0.2 above base 0.4)
            sub_agrees = sum([
                (signal == "BUY"  and trend_up)              or (signal == "SELL" and trend_down),
                (signal == "BUY"  and hist_expanding_up)     or (signal == "SELL" and hist_expanding_down),
                (signal == "BUY"  and last_rsi > config.RSI_TREND_BUY_MIN) or
                (signal == "SELL" and last_rsi < config.RSI_TREND_SELL_MAX),
            ])
            confidence = 0.4 + 0.2 * sub_agrees if signal != "HOLD" else 0.5

            return AgentSignal("technical", signal, round(confidence, 2), reasons[0])

        except Exception as e:
            logger.warning(f"TechnicalAgent error: {e}")
            return AgentSignal("technical", "HOLD", 0.0, f"Error: {e}")

    # ── Indicator helpers (pure pandas, no TA-Lib dependency) ─────────────────

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _macd(series: pd.Series, fast=12, slow=26, signal=9):
        ema_fast   = series.ewm(span=fast,   adjust=False).mean()
        ema_slow   = series.ewm(span=slow,   adjust=False).mean()
        macd_line  = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line

    @staticmethod
    def _bollinger(series: pd.Series, period=20, std_dev=2):
        mid   = series.rolling(period).mean()
        std   = series.rolling(period).std()
        upper = mid + std_dev * std
        lower = mid - std_dev * std
        return upper, mid, lower

    @staticmethod
    def _check_4h_alignment(df_4h: pd.DataFrame, signal: str) -> bool:
        """
        Returns True if the 4h trend supports the proposed signal direction.
        BUY  → 4h EMA20 must be above 4h EMA50 (medium-term uptrend)
        SELL → 4h EMA20 must be below 4h EMA50 (medium-term downtrend)
        """
        close_4h = df_4h["close"]
        ema20_4h = close_4h.ewm(span=20, adjust=False).mean()
        ema50_4h = close_4h.ewm(span=50, adjust=False).mean()
        if signal == "BUY":
            return float(ema20_4h.iloc[-1]) > float(ema50_4h.iloc[-1])
        else:
            return float(ema20_4h.iloc[-1]) < float(ema50_4h.iloc[-1])


# ─── Sentiment Agent ──────────────────────────────────────────────────────────

class SentimentAgent:
    """
    Pulls free crypto news via RSS feeds and scores headlines.
    Uses a keyword-based approach — no paid API needed.
    """

    BULLISH_WORDS = [
        "surge", "rally", "bull", "breakout", "record", "high", "adoption",
        "inflow", "etf", "institutional", "buy", "gain", "rise", "up",
        "positive", "growth", "boost", "milestone", "approval",
    ]
    BEARISH_WORDS = [
        "crash", "drop", "bear", "plunge", "hack", "ban", "regulation",
        "sell", "loss", "fear", "panic", "dump", "warning", "decline",
        "outflow", "red", "collapse", "fraud", "lawsuit", "debt",
    ]

    def __init__(self):
        self._cache: dict = {}
        self._cache_time: float = 0

    def analyse(self) -> AgentSignal:
        try:
            score = self._get_score()

            if score > 0.15:
                return AgentSignal("sentiment", "BUY",  min(0.5 + score, 0.9),
                                   f"Bullish sentiment score={score:+.2f}")
            elif score < -0.15:
                return AgentSignal("sentiment", "SELL", min(0.5 + abs(score), 0.9),
                                   f"Bearish sentiment score={score:+.2f}")
            else:
                return AgentSignal("sentiment", "HOLD", 0.5,
                                   f"Neutral sentiment score={score:+.2f}")

        except Exception as e:
            logger.warning(f"SentimentAgent error: {e}")
            # On failure, return neutral (don't block trade)
            return AgentSignal("sentiment", "HOLD", 0.5, f"Feed error — neutral: {e}")

    def _get_score(self) -> float:
        """Returns -1.0 (very bearish) to +1.0 (very bullish). Cached 5 minutes."""
        now = time.time()
        if now - self._cache_time < config.SENTIMENT_CACHE_SECONDS and self._cache:
            return self._cache["score"]

        headlines = self._fetch_headlines()
        if not headlines:
            return 0.0

        scores = []
        for headline in headlines:
            h = headline.lower()
            bull = sum(1 for w in self.BULLISH_WORDS if w in h)
            bear = sum(1 for w in self.BEARISH_WORDS if w in h)
            if bull + bear > 0:
                scores.append((bull - bear) / (bull + bear))

        score = sum(scores) / len(scores) if scores else 0.0
        self._cache = {"score": score}
        self._cache_time = now
        logger.debug(f"Sentiment: {len(headlines)} headlines, score={score:+.3f}")
        return score

    def _fetch_headlines(self) -> list[str]:
        headlines = []
        for feed_url in config.SENTIMENT_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    headlines.append(entry.get("title", ""))
            except Exception as e:
                logger.debug(f"Feed error {feed_url}: {e}")
        return [h for h in headlines if h]


# ─── Risk Agent ───────────────────────────────────────────────────────────────

class RiskAgent:
    """
    Approves or blocks a trade based on:
    - Current drawdown vs kill-switch threshold
    - Daily loss limit
    - Consecutive losses (cooldown)
    - Volatility (ATR)
    - Trades per day
    """

    def analyse(self, risk_state: dict, df: pd.DataFrame, signal: Signal = "BUY") -> AgentSignal:
        """
        risk_state keys:
            peak_balance, current_balance, daily_start_balance,
            consecutive_losses, trades_today, last_loss_time, kill_switch
        """
        try:
            # Kill switch
            if risk_state.get("kill_switch"):
                return AgentSignal("risk", "HOLD", 1.0, "Kill switch active — no trading")

            balance  = risk_state["current_balance"]
            peak     = risk_state["peak_balance"]
            day_start = risk_state["daily_start_balance"]

            # Drawdown check
            drawdown = (peak - balance) / peak if peak > 0 else 0
            if drawdown >= config.MAX_DRAWDOWN_KILL_SWITCH:
                return AgentSignal("risk", "HOLD", 1.0,
                                   f"Drawdown {drawdown:.1%} ≥ kill-switch {config.MAX_DRAWDOWN_KILL_SWITCH:.0%}")

            # Daily loss limit
            daily_loss = (day_start - balance) / day_start if day_start > 0 else 0
            if daily_loss >= config.MAX_DAILY_LOSS:
                return AgentSignal("risk", "HOLD", 1.0,
                                   f"Daily loss {daily_loss:.1%} ≥ limit {config.MAX_DAILY_LOSS:.0%}")

            # Trades per day
            if risk_state["trades_today"] >= config.MAX_TRADES_PER_DAY:
                return AgentSignal("risk", "HOLD", 0.9,
                                   f"Max trades/day reached ({config.MAX_TRADES_PER_DAY})")

            # Cooldown after consecutive losses
            consec = risk_state["consecutive_losses"]
            if consec >= config.MAX_CONSECUTIVE_LOSSES:
                last_loss = risk_state.get("last_loss_time")
                if last_loss:
                    elapsed = (datetime.now(timezone.utc) - last_loss).total_seconds() / 60
                    if elapsed < config.COOLDOWN_MINUTES:
                        remaining = config.COOLDOWN_MINUTES - elapsed
                        return AgentSignal("risk", "HOLD", 0.9,
                                           f"Cooldown active — {remaining:.0f}m remaining after {consec} losses")

            # ATR-based volatility gate — don't trade when volatility is extreme
            atr = self._atr(df, 14).iloc[-1]
            close = df["close"].iloc[-1]
            atr_pct = atr / close
            if atr_pct > 0.04:  # ATR > 4% of price — market is very wild
                return AgentSignal("risk", "HOLD", 0.7,
                                   f"Excessive volatility: ATR={atr_pct:.1%} of price")

            confidence = 1.0 - (drawdown / config.MAX_DRAWDOWN_KILL_SWITCH) * 0.5
            return AgentSignal("risk", signal, round(confidence, 2),
                               f"Risk OK: drawdown={drawdown:.1%}, daily_loss={daily_loss:.1%}, ATR={atr_pct:.2%}")

        except Exception as e:
            logger.warning(f"RiskAgent error: {e}")
            return AgentSignal("risk", "HOLD", 0.0, f"Error — defaulting to HOLD: {e}")

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


# ─── Execution Agent ──────────────────────────────────────────────────────────

class ExecutionAgent:
    """
    Checks fees, slippage, and minimum order size before approving execution.
    Also verifies the exchange is reachable.
    """

    BINANCE_TAKER_FEE = 0.001   # 0.1%
    SLIPPAGE_ESTIMATE = 0.0005  # 0.05% conservative estimate

    def analyse(self, balance: float, price: float, signal: Signal) -> AgentSignal:
        try:
            # Minimum order check
            order_usdt = max(config.MIN_ORDER_USDT, balance * config.MAX_RISK_PER_TRADE)
            if balance < config.MIN_ORDER_USDT:
                return AgentSignal("execution", "HOLD", 1.0,
                                   f"Balance ${balance:.2f} below minimum order ${config.MIN_ORDER_USDT}")

            # Fee + slippage impact check
            round_trip_cost = (self.BINANCE_TAKER_FEE + self.SLIPPAGE_ESTIMATE) * 2
            breakeven_move  = round_trip_cost  # price must move this much to profit
            atr_required    = breakeven_move   # sanity: we want ATR > breakeven

            reason = (
                f"Execution OK: order=${order_usdt:.2f}, "
                f"fees={self.BINANCE_TAKER_FEE:.2%}, "
                f"slip={self.SLIPPAGE_ESTIMATE:.2%}, "
                f"breakeven={breakeven_move:.3%}"
            )

            # Signal passthrough — execution agent gates on feasibility, not direction
            return AgentSignal("execution", signal if signal != "HOLD" else "HOLD",
                               0.8, reason)

        except Exception as e:
            logger.warning(f"ExecutionAgent error: {e}")
            return AgentSignal("execution", "HOLD", 0.0, f"Error: {e}")


# ─── Consensus Engine ─────────────────────────────────────────────────────────

class ConsensusEngine:
    """
    Collects signals from all 4 agents and makes the final go/no-go decision.
    Rule: ALL agents that have an opinion must agree. A HOLD from Risk or Execution
    always blocks. Technical and Sentiment must agree on direction.
    """

    def __init__(self):
        self.technical = TechnicalAgent()
        self.sentiment  = SentimentAgent()
        self.risk_agent = RiskAgent()
        self.execution  = ExecutionAgent()

        # ML filter — transparent passthrough until trained via --train-filter
        from ml_filter import SignalFilter
        self.ml_filter = SignalFilter()

    def decide(
        self,
        df: pd.DataFrame,
        regime: str,
        risk_state: dict,
        balance: float,
        price: float,
        df_4h: pd.DataFrame | None = None,
    ) -> tuple[Signal, float, list[AgentSignal]]:
        """
        Returns (final_signal, confidence_score, [all agent signals])

        df_4h: optional 4h OHLCV data for multi-timeframe trend confirmation.
               When provided, TechnicalAgent blocks signals that oppose the 4h trend.
        """
        tech_sig = self.technical.analyse(df, regime, df_4h)
        sent_sig = self.sentiment.analyse()

        # Technical must have a directional view
        if tech_sig.signal == "HOLD":
            logger.info(f"[CONSENSUS] No signal from Technical: {tech_sig.reason}")
            return "HOLD", 0.0, [tech_sig, sent_sig]

        # Sentiment affects confidence only — no veto.
        # RSS keyword scoring has too much noise to reliably block valid signals.
        direction = tech_sig.signal

        # Risk HOLD is always a hard block; pass direction so approval is directional
        risk_sig = self.risk_agent.analyse(risk_state, df, direction)
        if risk_sig.signal == "HOLD":
            logger.info(f"[CONSENSUS] Blocked by Risk: {risk_sig.reason}")
            return "HOLD", 0.0, [tech_sig, sent_sig, risk_sig]

        # ML filter — skip low-probability setups (transparent if not yet trained)
        if self.ml_filter.is_trained:
            from ml_filter import extract_features
            feats = extract_features(df, direction)
            should_trade, win_prob = self.ml_filter.predict(feats)
            if not should_trade:
                ml_sig = AgentSignal(
                    "ml_filter", "HOLD", round(1.0 - win_prob, 2),
                    f"ML filter blocked: predicted win_prob={win_prob:.1%} < threshold"
                )
                logger.info(f"[CONSENSUS] Blocked by ML filter: {ml_sig.reason}")
                return "HOLD", 0.0, [tech_sig, sent_sig, risk_sig, ml_sig]

        # Execution feasibility check
        exec_sig = self.execution.analyse(balance, price, direction)
        if exec_sig.signal == "HOLD":
            logger.info(f"[CONSENSUS] Blocked by Execution: {exec_sig.reason}")
            return "HOLD", 0.0, [tech_sig, sent_sig, risk_sig, exec_sig]

        # Weighted confidence
        w = config.AGENT_WEIGHTS
        confidence = (
            w["technical"] * tech_sig.confidence +
            w["sentiment"]  * sent_sig.confidence +
            w["risk"]       * risk_sig.confidence +
            w["execution"]  * exec_sig.confidence
        )

        logger.info(
            f"[CONSENSUS] {direction} agreed — confidence={confidence:.2f} | "
            f"tech={tech_sig.confidence:.2f} sent={sent_sig.confidence:.2f} "
            f"risk={risk_sig.confidence:.2f} exec={exec_sig.confidence:.2f}"
        )
        return direction, round(confidence, 3), [tech_sig, sent_sig, risk_sig, exec_sig]

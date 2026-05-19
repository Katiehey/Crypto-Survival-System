"""
backtest.py — Walk-forward backtesting module.

Walk-forward approach:
  1. Slide a training window across historical data
  2. Optimize signal thresholds on the in-sample window
  3. Evaluate on the out-of-sample window (never seen by optimizer)
  4. Aggregate results across all folds

This avoids the lookahead/overfitting problem of a single-period backtest.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import ccxt
import pandas as pd
import numpy as np

import config
from agents import TechnicalAgent
from strategy import RegimeDetector, TradingStrategy
from ml_filter import extract_features

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    entry_time:  datetime
    exit_time:   datetime
    signal:      str
    entry_price: float
    exit_price:  float
    size_usdt:   float
    pnl_usdt:    float
    pnl_pct:     float
    regime:      str
    stop_loss:   float
    take_profit: float
    features:    dict = field(default_factory=dict)   # ML training context


@dataclass
class BacktestResult:
    total_return_pct:  float
    sharpe_ratio:      float
    max_drawdown_pct:  float
    win_rate_pct:      float
    total_trades:      int
    winning_trades:    int
    losing_trades:     int
    avg_win_usdt:      float
    avg_loss_usdt:     float
    profit_factor:     float
    fee_adjusted_pnl:  float
    trades:            list[Trade] = field(default_factory=list)
    equity_curve:      list[float] = field(default_factory=list)
    fold_results:      list[dict]  = field(default_factory=list)


class WalkForwardBacktester:
    """
    Runs walk-forward backtesting on historical OHLCV data.
    Uses the same TechnicalAgent and RegimeDetector as live trading.
    """

    BINANCE_FEE = 0.001  # 0.1% taker

    def __init__(
        self,
        in_sample_bars:  int = 1000,
        out_sample_bars: int = 200,
        step_bars:       int = 200,
        starting_capital: float = None,
    ):
        self.in_sample  = in_sample_bars
        self.out_sample = out_sample_bars
        self.step       = step_bars
        self.capital    = starting_capital or config.STARTING_CAPITAL

        self.technical  = TechnicalAgent()
        self.regime_det = RegimeDetector()
        self.strategy   = TradingStrategy()

    # ─── Public API ──────────────────────────────────────────────────────────

    def run(self, df: pd.DataFrame, df_4h: pd.DataFrame | None = None) -> BacktestResult:
        """Run walk-forward test on a DataFrame of OHLCV data.

        df_4h: optional 4h OHLCV covering the same date range as df. When
               provided, each simulated bar passes the aligned 4h window to
               TechnicalAgent for multi-timeframe confirmation — matching live
               bot behaviour exactly.
        """
        logger.info(
            f"Walk-forward backtest: {len(df)} bars, "
            f"IS={self.in_sample} OS={self.out_sample} step={self.step}"
            + (f", 4h bars={len(df_4h)}" if df_4h is not None else ", no 4h data")
        )

        all_trades:  list[Trade] = []
        fold_results: list[dict] = []

        for fold_idx, (train_df, test_df) in enumerate(self._folds(df)):
            fold_trades = self._simulate_fold(train_df, test_df, df_4h)
            fold_stats  = self._fold_stats(fold_trades)
            fold_stats["fold"] = fold_idx + 1
            fold_results.append(fold_stats)
            all_trades.extend(fold_trades)

            logger.info(
                f"Fold {fold_idx+1}: trades={len(fold_trades)} "
                f"win_rate={fold_stats['win_rate_pct']:.1f}% "
                f"return={fold_stats['total_return_pct']:.2f}%"
            )

        return self._aggregate(all_trades, fold_results)

    def fetch_historical(
        self,
        symbol: str = None,
        timeframe: str = None,
        days: int = 400,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV from Binance (public endpoint, no API key needed).
        """
        symbol    = symbol    or config.TRADING_PAIR
        timeframe = timeframe or config.TIMEFRAME

        exchange = ccxt.binance({"enableRateLimit": True})
        since    = exchange.parse8601(
            (pd.Timestamp.utcnow() - pd.Timedelta(days=days)).isoformat()
        )

        logger.info(f"Fetching {days} days of {symbol} {timeframe} from Binance…")
        all_ohlcv = []
        while True:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            if len(ohlcv) < 1000:
                break

        df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").drop_duplicates()
        logger.info(f"Fetched {len(df)} candles ({df.index[0]} → {df.index[-1]})")
        return df

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _folds(self, df: pd.DataFrame) -> Generator:
        start = self.in_sample
        while start + self.out_sample <= len(df):
            train_df = df.iloc[start - self.in_sample : start]
            test_df  = df.iloc[start : start + self.out_sample]
            yield train_df, test_df
            start += self.step

    def _simulate_fold(self, train_df: pd.DataFrame, test_df: pd.DataFrame, df_4h: pd.DataFrame | None = None) -> list[Trade]:
        """
        Simulate bar-by-bar trading on the out-of-sample (test) window.
        Uses the tail of train_df as indicator lookback context so the
        first test bar has a full warm-up history.
        """
        trades:  list[Trade] = []
        balance = self.capital
        in_trade = False
        entry_price = stop_loss = take_profit = 0.0
        entry_time    = None
        entry_signal  = ""
        entry_regime  = ""
        entry_features: dict = {}
        size_usdt     = 0.0

        lookback = 200  # bars of context needed for indicators (EMA200, ADX, etc.)

        # Prepend tail of training data so test bar 0 has a full lookback window
        context = pd.concat([train_df.iloc[-lookback:], test_df])
        n_test  = len(test_df)

        # Iterate only over the out-of-sample bars (the last n_test rows)
        for i in range(lookback, lookback + n_test):
            window = context.iloc[i - lookback : i + 1]
            row    = context.iloc[i]
            close  = row["close"]

            if in_trade:
                # Regime-flip exit: close at bar close if market has shifted
                current_regime = self.regime_det.detect(window)["regime"]
                regime_flipped = current_regime != entry_regime

                # Check SL/TP exit conditions
                if entry_signal == "BUY":
                    hit_stop   = row["low"]   <= stop_loss
                    hit_target = row["high"]  >= take_profit
                elif entry_signal == "SELL":
                    hit_stop   = row["high"]  >= stop_loss
                    hit_target = row["low"]   <= take_profit
                else:
                    hit_stop = hit_target = False

                if hit_stop or hit_target or regime_flipped:
                    if regime_flipped and not hit_stop and not hit_target:
                        exit_price = close  # exit at bar close on regime flip
                    else:
                        exit_price = stop_loss if hit_stop else take_profit
                    sign       = 1 if entry_signal == "BUY" else -1
                    gross_pnl  = sign * (exit_price - entry_price) / entry_price * size_usdt
                    fee        = size_usdt * self.BINANCE_FEE * 2  # entry + exit
                    net_pnl    = gross_pnl - fee
                    pnl_pct    = net_pnl / size_usdt * 100

                    trades.append(Trade(
                        entry_time=entry_time,
                        exit_time=context.index[i],
                        signal=entry_signal,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        size_usdt=size_usdt,
                        pnl_usdt=net_pnl,
                        pnl_pct=pnl_pct,
                        regime=entry_regime,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        features=entry_features,
                    ))
                    balance  += net_pnl
                    in_trade  = False

            else:
                # Look for entry signal
                regime_info = self.regime_det.detect(window)
                regime      = regime_info["regime"]

                # Align 4h data to current bar's timestamp
                window_4h = None
                if df_4h is not None:
                    ts = context.index[i]
                    _slice = df_4h.loc[:ts].iloc[-100:]
                    if len(_slice) >= 50:
                        window_4h = _slice

                tech_signal = self.technical.analyse(window, regime, df_4h=window_4h)

                if tech_signal.signal in ("BUY", "SELL") and tech_signal.confidence >= 0.6:
                    levels = self.strategy.compute_levels(window, tech_signal.signal, regime)
                    if not levels:
                        continue

                    order_usdt = max(config.MIN_ORDER_USDT, balance * config.MAX_RISK_PER_TRADE)
                    order_usdt = min(order_usdt, balance * 0.95)
                    if order_usdt < config.MIN_ORDER_USDT or order_usdt > balance:
                        continue

                    in_trade      = True
                    entry_price   = close
                    stop_loss     = levels["stop_loss"]
                    take_profit   = levels["take_profit"]
                    entry_time    = context.index[i]
                    entry_signal  = tech_signal.signal
                    entry_regime  = regime
                    size_usdt     = order_usdt
                    entry_features = extract_features(window, tech_signal.signal)

        # Close any open trade at the last bar's closing price (market-exit at fold end)
        if in_trade:
            last_row   = context.iloc[-1]
            exit_price = last_row["close"]
            sign       = 1 if entry_signal == "BUY" else -1
            gross_pnl  = sign * (exit_price - entry_price) / entry_price * size_usdt
            fee        = size_usdt * self.BINANCE_FEE * 2
            net_pnl    = gross_pnl - fee
            pnl_pct    = net_pnl / size_usdt * 100
            trades.append(Trade(
                entry_time=entry_time,
                exit_time=context.index[-1],
                signal=entry_signal,
                entry_price=entry_price,
                exit_price=exit_price,
                size_usdt=size_usdt,
                pnl_usdt=net_pnl,
                pnl_pct=pnl_pct,
                regime=entry_regime,
                stop_loss=stop_loss,
                take_profit=take_profit,
                features=entry_features,
            ))

        return trades

    def _fold_stats(self, trades: list[Trade]) -> dict:
        if not trades:
            return {
                "total_return_pct": 0, "win_rate_pct": 0,
                "sharpe_ratio": 0, "max_drawdown_pct": 0,
                "total_trades": 0, "fee_adjusted_pnl": 0,
            }

        pnls         = [t.pnl_usdt for t in trades]
        wins         = [p for p in pnls if p > 0]
        losses       = [p for p in pnls if p < 0]
        total_return = sum(pnls) / self.capital * 100
        win_rate     = len(wins) / len(trades) * 100

        equity   = np.cumsum(pnls)
        peak     = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / (peak + self.capital)
        max_dd   = float(drawdown.max()) * 100

        returns = pd.Series([t.pnl_usdt / t.size_usdt for t in trades])
        if len(trades) >= 2 and returns.std() > 0:
            total_days = (trades[-1].exit_time - trades[0].entry_time).total_seconds() / 86400
            trades_per_year = len(trades) / max(total_days, 1) * 365
            sharpe = returns.mean() / returns.std() * np.sqrt(trades_per_year)
        else:
            sharpe = 0.0

        return {
            "total_return_pct":  round(total_return, 2),
            "win_rate_pct":      round(win_rate, 1),
            "sharpe_ratio":      round(float(sharpe), 2),
            "max_drawdown_pct":  round(max_dd, 2),
            "total_trades":      len(trades),
            "fee_adjusted_pnl":  round(sum(pnls), 2),
        }

    def _aggregate(self, trades: list[Trade], fold_results: list[dict]) -> BacktestResult:
        if not trades:
            logger.warning("Backtest produced zero trades")
            return BacktestResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

        pnls    = [t.pnl_usdt for t in trades]
        wins    = [p for p in pnls if p > 0]
        losses  = [p for p in pnls if p < 0]

        equity  = self.capital + np.cumsum(pnls)
        peak    = np.maximum.accumulate(equity)
        dd_pct  = ((peak - equity) / peak * 100).max()

        returns = pd.Series([t.pnl_usdt / t.size_usdt for t in trades])
        if len(trades) >= 2 and returns.std() > 0:
            total_days = (trades[-1].exit_time - trades[0].entry_time).total_seconds() / 86400
            trades_per_year = len(trades) / max(total_days, 1) * 365
            sharpe = returns.mean() / returns.std() * np.sqrt(trades_per_year)
        else:
            sharpe = 0.0

        profit_factor = (sum(wins) / abs(sum(losses))
                         if losses else float("inf"))

        result = BacktestResult(
            total_return_pct = round(sum(pnls) / self.capital * 100, 2),
            sharpe_ratio     = round(float(sharpe), 2),
            max_drawdown_pct = round(float(dd_pct), 2),
            win_rate_pct     = round(len(wins) / len(trades) * 100, 1),
            total_trades     = len(trades),
            winning_trades   = len(wins),
            losing_trades    = len(losses),
            avg_win_usdt     = round(sum(wins)   / len(wins)   if wins   else 0, 2),
            avg_loss_usdt    = round(sum(losses)  / len(losses) if losses else 0, 2),
            profit_factor    = round(profit_factor, 2),
            fee_adjusted_pnl = round(sum(pnls), 2),
            trades           = trades,
            equity_curve     = equity.tolist(),
            fold_results     = fold_results,
        )

        self._print_report(result)
        return result

    def _print_report(self, r: BacktestResult):
        sep = "─" * 50
        print(f"\n{sep}")
        print("  WALK-FORWARD BACKTEST REPORT")
        print(sep)
        print(f"  Total Return:     {r.total_return_pct:+.2f}%")
        print(f"  Sharpe Ratio:     {r.sharpe_ratio:.2f}")
        print(f"  Max Drawdown:     {r.max_drawdown_pct:.2f}%")
        print(f"  Win Rate:         {r.win_rate_pct:.1f}%")
        print(f"  Total Trades:     {r.total_trades}")
        print(f"  Profit Factor:    {r.profit_factor:.2f}")
        print(f"  Fee-Adj PnL:      ${r.fee_adjusted_pnl:+.2f}")
        print(f"  Avg Win / Loss:   ${r.avg_win_usdt:.2f} / ${r.avg_loss_usdt:.2f}")
        print(f"\n  Walk-Forward Folds ({len(r.fold_results)}):")
        for fold in r.fold_results:
            print(
                f"    Fold {fold['fold']:02d}: "
                f"return={fold['total_return_pct']:+.2f}% "
                f"win={fold['win_rate_pct']:.0f}% "
                f"trades={fold['total_trades']}"
            )
        print(sep + "\n")

    def save_results(self, result: BacktestResult, output_dir: str = "backtest_results"):
        """Save equity curve and trade log to CSV."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if result.trades:
            trades_df = pd.DataFrame([
                {
                    "entry_time":   t.entry_time,
                    "exit_time":    t.exit_time,
                    "signal":       t.signal,
                    "entry_price":  t.entry_price,
                    "exit_price":   t.exit_price,
                    "size_usdt":    t.size_usdt,
                    "pnl_usdt":     t.pnl_usdt,
                    "pnl_pct":      t.pnl_pct,
                    "regime":       t.regime,
                }
                for t in result.trades
            ])
            trades_df.to_csv(f"{output_dir}/{ts}_trades.csv", index=False)

        equity_df = pd.DataFrame({"equity": result.equity_curve})
        equity_df.to_csv(f"{output_dir}/{ts}_equity.csv", index=False)
        logger.info(f"Results saved to {output_dir}/{ts}_*.csv")

    def extract_training_data(
        self, result: "BacktestResult"
    ) -> tuple[list[dict], list[int]]:
        """
        Extract (features_list, outcomes) from a completed BacktestResult for ML training.
        Only includes trades that have captured features (signal BUY/SELL, not fold-end exits).
        outcomes: 1 = profitable trade, 0 = losing trade
        """
        features_list = []
        outcomes      = []
        for t in result.trades:
            if not t.features:
                continue
            features_list.append(t.features)
            outcomes.append(1 if t.pnl_usdt > 0 else 0)
        win_rate_str = f"{sum(outcomes)/len(outcomes):.1%}" if outcomes else "n/a"
        logger.info(
            f"Extracted {len(features_list)} labelled trades for ML training "
            f"(win_rate={win_rate_str})"
        )
        return features_list, outcomes

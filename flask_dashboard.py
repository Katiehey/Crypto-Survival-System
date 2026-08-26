"""
flask_dashboard.py — Browser-based dashboard for Crypto Survival System.

Run alongside bot.py in a separate tmux window:
    python flask_dashboard.py

Then open in your browser: http://<oracle-ip>:5000
(Oracle: open port 5000 in VCN security list + sudo firewall-cmd --add-port=5000/tcp --permanent)
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import base64
import functools
import os

import ccxt
import pandas as pd
import psutil
from flask import Flask, jsonify, request, Response

import config
from strategy import RegimeDetector

app = Flask(__name__)
_start_time = time.monotonic()

_DASH_USER = os.getenv("DASHBOARD_USER", "admin")
_DASH_PASS = os.getenv("DASHBOARD_PASS", "")

def _require_auth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not _DASH_PASS:
            return f(*args, **kwargs)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                user, pw = base64.b64decode(auth[6:]).decode().split(":", 1)
                if user == _DASH_USER and pw == _DASH_PASS:
                    return f(*args, **kwargs)
            except Exception:
                pass
        return Response("Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Crypto Dashboard"'})
    return wrapper
_cache: dict = {}
_cache_ts: float = 0.0
CACHE_TTL = 25  # seconds — refresh faster than the 30s JS poll


# ─── Exchange ─────────────────────────────────────────────────────────────────

def _build_exchange():
    if config.EXCHANGE == "kucoin":
        return ccxt.kucoin({"enableRateLimit": True})
    return ccxt.binance({"enableRateLimit": True})


# ─── Indicators ───────────────────────────────────────────────────────────────

def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, 1e-10)
    return float((100 - (100 / (1 + rs))).iloc[-1])


def _bollinger(series: pd.Series, period: int = 20, std_dev: int = 2):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    return float((mid + std_dev * std).iloc[-1]), float((mid - std_dev * std).iloc[-1])


# ─── Data fetcher ─────────────────────────────────────────────────────────────

def fetch_data() -> dict[str, Any]:
    global _cache, _cache_ts
    if time.monotonic() - _cache_ts < CACHE_TTL and _cache:
        return _cache

    d: dict[str, Any] = {
        "price": 0, "price_change": 0, "regime": "unknown", "adx": 0,
        "rsi": 0, "macd_hist": 0, "macd_cross_up": False,
        "ema20": 0, "ema50": 0, "ema200": 0,
        "bb_lower": 0, "bb_upper": 0, "vol_ratio": 0,
        "plus_di": 0, "minus_di": 0,
        "ema20_4h": 0, "ema50_4h": 0,
        "timeframe": config.TIMEFRAME, "htf": config.HTF_TIMEFRAME,
        "ml_filter_trained": False, "ml_filter_n": 0,
        "rsi_threshold": config.RSI_TREND_BUY_MIN,
        "adx_threshold": config.ADX_TREND_THRESHOLD,
        "vol_threshold": config.VOLUME_SPIKE_MIN,
        "drawdown_threshold": config.MAX_DRAWDOWN_KILL_SWITCH * 100,
        "balance": config.STARTING_CAPITAL, "peak": config.STARTING_CAPITAL,
        "drawdown_pct": 0, "daily_pnl": 0,
        "trades_today": 0, "max_trades_per_day": config.MAX_TRADES_PER_DAY, "total_trades": 0,
        "win_trades": 0, "loss_trades": 0,
        "win_rate": 0, "profit_factor": 0,
        "best_trade": 0, "worst_trade": 0,
        "recent_trades": [],
        "price_history": [],
        "bid_depth_usdt": 0, "ask_depth_usdt": 0,
        "price_impact_pct": 0, "depth_ok": True,
        "cpu_pct": 0, "ram_used_mb": 0, "ram_total_mb": 0,
        "last_updated": "—", "uptime": "00:00:00", "error": "",
        "hmm_regime": "", "hmm_confidence": 0.0, "hmm_fallback": True,
        # Active strategy + trend-filter state (what the bot ACTUALLY trades on).
        "strategy": getattr(config, "STRATEGY", "consensus"),
        "chart_timeframe": config.TIMEFRAME,
        "equity": config.STARTING_CAPITAL, "unrealized_pnl": 0.0,
        "unrealized_pct": 0.0, "position_entry": 0.0, "position_size": 0.0,
        "position_value": 0.0, "position_opened": "",
        "trend_sma_period": getattr(config, "TREND_SMA_PERIOD", 150),
        "trend_sma": 0, "trend_close": 0, "trend_gap_pct": 0,
        "trend_want_long": False, "trend_position": "unknown",
    }

    try:
        exchange = _build_exchange()
        symbol   = config.TRADING_PAIR

        # ── primary OHLCV ─────────────────────────────────────────────────────
        # Must match config.TIMEFRAME. Hardcoding "1h" here made the dashboard
        # compute RSI/EMA/MACD/ADX on a different timeframe than the bot trades,
        # so the Signal Heat panel showed conditions the bot was not acting on.
        ohlcv = exchange.fetch_ohlcv(symbol, config.TIMEFRAME, limit=300)
        df    = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
        close = df["close"]

        d["price"]        = float(close.iloc[-1])
        d["price_change"] = (d["price"] - float(close.iloc[-25])) / float(close.iloc[-25]) * 100
        d["price_history"] = [round(float(x), 2) for x in close.tail(48).tolist()]

        # Indicators
        d["rsi"] = _rsi(close)

        ema_fast  = close.ewm(span=12, adjust=False).mean()
        ema_slow  = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        sig_line  = macd_line.ewm(span=9, adjust=False).mean()
        d["macd_hist"]    = float((macd_line - sig_line).iloc[-1])
        d["macd_cross_up"] = bool(
            macd_line.iloc[-1] > sig_line.iloc[-1] and
            macd_line.iloc[-2] <= sig_line.iloc[-2]
        )
        d["ema20"]  = float(close.ewm(span=20,  adjust=False).mean().iloc[-1])
        d["ema50"]  = float(close.ewm(span=50,  adjust=False).mean().iloc[-1])
        d["ema200"] = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
        d["bb_upper"], d["bb_lower"] = _bollinger(close)

        vol_avg      = float(df["volume"].rolling(50).mean().iloc[-1])
        d["vol_ratio"] = float(df["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 0.0

        ri            = RegimeDetector().detect(df)
        d["regime"]   = ri["regime"]
        d["adx"]      = ri["adx"]
        d["plus_di"]  = ri["plus_di"]
        d["minus_di"] = ri["minus_di"]
        d["hmm_regime"]     = ri.get("hmm_regime") or ""
        d["hmm_confidence"] = ri.get("hmm_confidence", 0.0)
        d["hmm_fallback"]   = ri.get("hmm_fallback", True)

        # Report the ML filter's ACTUAL state. The old hardcoded label read
        # "bypass (<200 trades)" -- the real minimum is MIN_TRADES_TO_TRAIN (20),
        # and whether it is active depends on ops/signal_filter.pkl existing.
        try:
            from ml_filter import SignalFilter
            _sf = SignalFilter()
            d["ml_filter_trained"] = bool(_sf.is_trained)
            d["ml_filter_n"] = int((_sf._model or {}).get("n_samples", 0)) if _sf.is_trained else 0
        except Exception:
            pass

        d["rsi_threshold"] = (
            config.RSI_RANGE_BUY_MAX if d["regime"] == "ranging"
            else config.RSI_TREND_BUY_MIN
        )

        # ── higher-timeframe OHLCV (MTF confirmation) ─────────────────────────
        # Mirrors the bot's ExecutionAgent, which uses config.HTF_TIMEFRAME.
        ohlcv_4h = exchange.fetch_ohlcv(symbol, config.HTF_TIMEFRAME, limit=100)
        df4      = pd.DataFrame(ohlcv_4h, columns=["ts","open","high","low","close","volume"])
        c4       = df4["close"]
        d["ema20_4h"] = float(c4.ewm(span=20, adjust=False).mean().iloc[-1])
        d["ema50_4h"] = float(c4.ewm(span=50, adjust=False).mean().iloc[-1])

        # ── Trend-filter state (the live strategy) ────────────────────────────
        # Compute the same long/flat signal the bot uses, and read the position it
        # persisted. Wrapped so a data hiccup never takes down the dashboard.
        if getattr(config, "STRATEGY", "") == "trend_filter":
            try:
                period = config.TREND_SMA_PERIOD
                d_ohlcv = exchange.fetch_ohlcv(symbol, config.TREND_TIMEFRAME, limit=period + 50)
                dclose = pd.DataFrame(d_ohlcv, columns=["ts","open","high","low","close","volume"])["close"]
                dclose = dclose.iloc[:-1]  # drop forming candle, mirror the bot
                sma = float(dclose.rolling(period).mean().iloc[-1])
                last = float(dclose.iloc[-1])
                d["trend_sma"] = sma
                d["trend_close"] = last
                d["trend_gap_pct"] = (last - sma) / sma * 100 if sma else 0
                d["trend_want_long"] = last > sma
                st = json.loads(Path(config.TREND_STATE_FILE).read_text()) \
                    if Path(config.TREND_STATE_FILE).exists() else {}
                d["trend_position"] = st.get("position", "unknown")

                # Mark the OPEN position to market. The trades table only holds
                # completed round trips, so while this strategy holds (months at a
                # time) the account reads as flat and unchanged — it showed $29.93
                # / $0.00 PnL while sitting on a +13% unrealised gain.
                if st.get("balance") is not None:
                    d["balance"] = float(st["balance"])       # bot is authoritative
                    d["_balance_from_bot"] = True
                det = st.get("position_detail") or {}
                if d["trend_position"] == "long" and det.get("entry_price"):
                    entry = float(det["entry_price"])
                    size  = float(det.get("size_usdt") or 0)
                    live  = float(d["price"] or last)
                    d["position_entry"]   = entry
                    d["position_size"]    = size
                    d["position_value"]   = size * (live / entry) if entry else 0.0
                    d["unrealized_pnl"]   = d["position_value"] - size
                    d["unrealized_pct"]   = (live / entry - 1) * 100 if entry else 0.0
                    d["equity"]           = d["balance"] + d["unrealized_pnl"]
                    d["position_opened"]  = det.get("entered_at", "")
                else:
                    d["equity"] = d["balance"]
                # The price chart defaults to config.TIMEFRAME (4h), but this
                # strategy decides on daily candles — showing 4h means watching a
                # different series than the one making decisions. Reuse the daily
                # closes already fetched above.
                d["price_history"] = [round(float(x), 2) for x in dclose.tail(60).tolist()]
                d["chart_timeframe"] = config.TREND_TIMEFRAME
            except Exception as e:
                d["error"] = f"trend state: {e}"

        # ── Order book depth (KuCoin CEX, not KCC chain) ──────────────────────
        try:
            ob    = exchange.fetch_order_book(symbol, limit=20)
            price = d["price"]
            rng   = 0.001  # ±0.1% of mid price
            bid_depth = sum(qty * pr for pr, qty in ob["bids"] if pr >= price * (1 - rng))
            ask_depth = sum(qty * pr for pr, qty in ob["asks"] if pr <= price * (1 + rng))
            d["bid_depth_usdt"] = int(bid_depth)
            d["ask_depth_usdt"] = int(ask_depth)
            trade_size = float(getattr(config, "MIN_ORDER_USDT", 11.0))
            impact = (trade_size / bid_depth * 100) if bid_depth > 0 else 0.0
            d["price_impact_pct"] = round(impact, 5)
            d["depth_ok"] = impact < 0.05
        except Exception:
            pass  # order book is optional — don't crash the whole dashboard

        # ── Database ──────────────────────────────────────────────────────────
        if Path(config.DB_PATH).exists():
            conn      = sqlite3.connect(config.DB_PATH)
            all_pnl   = pd.read_sql("SELECT pnl_usdt FROM trades ORDER BY id ASC", conn)
            total_count = pd.read_sql("SELECT COUNT(*) as cnt FROM trades", conn)
            trades    = pd.read_sql("SELECT * FROM trades ORDER BY id DESC LIMIT 100", conn)
            conn.close()

            if not all_pnl.empty:
                # Seed the series with STARTING_CAPITAL: without it the equity curve
                # begins AFTER the first trade, so a first losing trade sets the peak
                # to the already-reduced balance and drawdown reads 0.00% forever.
                curve              = config.STARTING_CAPITAL + all_pnl["pnl_usdt"].cumsum()
                equity             = pd.concat([pd.Series([float(config.STARTING_CAPITAL)]), curve],
                                               ignore_index=True)
                # Don't clobber the bot's own balance. Under trend_filter the bot
                # persists its live figure (which includes the open position's entry
                # fee); re-deriving it from closed trades alone drops that fee and
                # leaves equity - unrealised != cash on screen.
                if not d.get("_balance_from_bot"):
                    d["balance"]   = float(equity.iloc[-1])
                d["peak"]          = float(equity.max())
                d["drawdown_pct"]  = max(0.0, (d["peak"] - d["balance"]) / d["peak"] * 100)
                d["total_trades"]  = int(total_count["cnt"].iloc[0])

            if not trades.empty:
                d["recent_trades"] = trades.head(10).to_dict("records")
                today   = datetime.now(timezone.utc).date().isoformat()
                today_t = trades[trades["timestamp"].str.startswith(today)]
                d["trades_today"] = len(today_t)
                d["daily_pnl"]    = float(today_t["pnl_usdt"].sum()) if not today_t.empty else 0.0

                wins   = trades[trades["pnl_usdt"] > 0]
                losses = trades[trades["pnl_usdt"] < 0]
                d["win_trades"]  = len(wins)
                d["loss_trades"] = len(losses)
                d["win_rate"]    = round(len(wins) / len(trades) * 100, 1)
                gross_win  = float(wins["pnl_usdt"].sum())   if not wins.empty   else 0.0
                gross_loss = abs(float(losses["pnl_usdt"].sum())) if not losses.empty else 0.0
                d["profit_factor"] = round(gross_win / gross_loss, 2) if gross_loss > 0 else 0.0
                d["best_trade"]  = round(float(trades["pnl_usdt"].max()), 4)
                d["worst_trade"] = round(float(trades["pnl_usdt"].min()), 4)

        # ── System ────────────────────────────────────────────────────────────
        d["cpu_pct"]    = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        d["ram_used_mb"]  = int(mem.used  / 1024 / 1024)
        d["ram_total_mb"] = int(mem.total / 1024 / 1024)

        uptime_s = int(time.monotonic() - _start_time)
        h, r = divmod(uptime_s, 3600)
        m, s = divmod(r, 60)
        d["uptime"]       = f"{h:02d}:{m:02d}:{s:02d}"
        d["last_updated"] = datetime.now().strftime("%H:%M:%S")

    except Exception as e:
        d["error"] = str(e)[:150]

    _cache    = d
    _cache_ts = time.monotonic()
    return d


# ─── HTML (served statically — no Jinja2 rendering, JS handles all data) ─────

HTML = """<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crypto Survival System</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { background:#0d1117; color:#e6edf3; font-family:'Segoe UI',system-ui,sans-serif; }
  .card { background:#161b22; border:1px solid #30363d; }
  .card-header { background:#21262d; border-bottom:1px solid #30363d; font-size:.85rem; letter-spacing:.05em; }
  .price-big { font-size:2.2rem; font-weight:700; letter-spacing:-1px; }
  .g-pos { color:#3fb950; } .g-neg { color:#f85149; } .g-dim { color:#8b949e; }
  .progress { height:8px; background:#21262d; border-radius:4px; }
  .stat-label { color:#8b949e; font-size:.75rem; margin-bottom:1px; }
  .stat-value { font-weight:600; font-size:.92rem; }
  .orb { width:76px; height:76px; border-radius:50%; display:flex; align-items:center;
         justify-content:center; font-size:1.4rem; font-weight:700; margin:0 auto; }
  .orb-go   { background:#1a4a2a; border:3px solid #3fb950; color:#3fb950; box-shadow:0 0 18px #3fb95055; }
  .orb-part { background:#3a2a0a; border:3px solid #e3b341; color:#e3b341; box-shadow:0 0 18px #e3b34155; }
  .orb-wait { background:#1a1a2a; border:3px solid #30363d; color:#8b949e; }
  .pulse-dot { display:inline-block; width:8px; height:8px; border-radius:50%;
               background:#3fb950; animation:pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.25} }
  .heat-label { font-size:.72rem; color:#8b949e; }
  .heat-value { font-size:.72rem; font-weight:600; }
  .footer-bar { background:#161b22; border-top:1px solid #30363d; padding:6px 16px;
                font-size:.72rem; color:#8b949e; }
  table.table-trades td { font-size:.75rem; vertical-align:middle; padding:.3rem .5rem; }
</style>
</head>
<body>

<!-- HEADER -->
<div class="d-flex flex-wrap align-items-center px-4 py-2 gap-3"
     style="background:#161b22;border-bottom:1px solid #30363d;min-height:54px">
  <span style="font-weight:700;color:#58a6ff;font-size:.9rem">⬡ CRYPTO SURVIVAL</span>
  <span class="price-big" id="price">$—</span>
  <span class="fs-5" id="price-change">—</span>
  <span id="regime-badge">—</span>
  <span class="g-dim" id="adx-val" style="font-size:.8rem">ADX —</span>
  <span id="hmm-header-badge" style="font-size:.78rem"></span>
  <span id="legacy-tag" class="g-dim"
        style="font-size:.68rem;border:1px solid #30363d;border-radius:3px;padding:0 4px"></span>
  <span class="ms-auto d-flex align-items-center gap-2">
    <span class="pulse-dot" id="pulse-dot"></span>
    <span class="g-dim" id="last-updated" style="font-size:.78rem">—</span>
    <span class="g-dim" id="countdown" style="font-size:.78rem"></span>
  </span>
  <span class="text-danger" id="error-msg" style="font-size:.75rem"></span>
</div>

<div class="container-fluid p-3">

<!-- STRATEGY BANNER: what the bot is ACTUALLY trading on -->
<div class="card mb-3" id="strategy-banner">
  <div class="card-body py-2 d-flex flex-wrap align-items-center gap-3">
    <span class="fw-bold">ACTIVE STRATEGY</span>
    <span class="badge bg-secondary" id="strategy-name" style="font-size:.8rem">—</span>
    <span id="trend-state" style="font-size:.85rem"></span>
    <span class="g-dim ms-auto" id="trend-note" style="font-size:.72rem"></span>
  </div>
</div>

<div class="row g-3">

  <!-- COL A: Signal Orb + Account -->
  <div class="col-md-3">
    <div class="card mb-3">
      <div class="card-header fw-bold">SIGNAL STATUS</div>
      <div class="card-body text-center py-3">
        <div class="orb orb-wait mb-2" id="signal-orb">⏳</div>
        <div id="signal-text" class="g-dim fw-bold mt-1">WAITING</div>
        <div class="g-dim mt-1" id="conds-met" style="font-size:.72rem">0 / 4 conditions</div>
      </div>
    </div>
    <div class="card">
      <div class="card-header fw-bold">ACCOUNT</div>
      <div class="card-body p-3">
        <div class="row g-2">
          <div class="col-6"><div class="stat-label">Equity</div><div class="stat-value" id="equity">$—</div></div>
          <div class="col-6"><div class="stat-label">Unrealised</div><div class="stat-value" id="unrealized">—</div></div>
          <div class="col-6"><div class="stat-label">Cash</div><div class="stat-value" id="balance">$—</div></div>
          <div class="col-6"><div class="stat-label">Peak</div><div class="stat-value" id="peak">$—</div></div>
          <div class="col-6"><div class="stat-label">Drawdown</div><div class="stat-value" id="drawdown">—</div></div>
          <div class="col-6"><div class="stat-label">PnL Today</div><div class="stat-value" id="daily-pnl">—</div></div>
          <div class="col-6"><div class="stat-label">Trades Today</div><div class="stat-value" id="trades-today">—</div></div>
          <div class="col-6"><div class="stat-label">Total Trades</div><div class="stat-value" id="total-trades">—</div></div>
          <div class="col-6"><div class="stat-label">Win Rate</div><div class="stat-value" id="win-rate">—</div></div>
          <div class="col-6"><div class="stat-label">Profit Factor</div><div class="stat-value" id="profit-factor">—</div></div>
          <div class="col-6"><div class="stat-label">Best Trade</div><div class="stat-value g-pos" id="best-trade">—</div></div>
          <div class="col-6"><div class="stat-label">Worst Trade</div><div class="stat-value g-neg" id="worst-trade">—</div></div>
        </div>
      </div>
    </div>
  </div>

  <!-- COL B: Signal Heat -->
  <div class="col-md-4">
    <div class="card" style="height:100%">
      <div class="card-header fw-bold d-flex justify-content-between align-items-center">
        <span>SIGNAL HEAT</span>
        <span class="badge" id="regime-heat-badge" style="font-size:.7rem">—</span>
      </div>
      <div class="card-body p-3" id="heat-body"></div>
    </div>
  </div>

  <!-- COL C: Agents + Order Book -->
  <div class="col-md-5">
    <div class="card mb-3">
      <div class="card-header fw-bold">AGENT VOTES</div>
      <div class="card-body p-2">
        <div class="row g-1" id="agents-body"></div>
      </div>
    </div>
    <div class="card">
      <div class="card-header fw-bold d-flex justify-content-between align-items-center">
        <span>ORDER BOOK DEPTH <small class="g-dim">(±0.1% of mid)</small></span>
        <span class="badge" id="depth-badge" style="font-size:.7rem">—</span>
      </div>
      <div class="card-body p-3">
        <div class="d-flex justify-content-between mb-1">
          <small class="g-pos">BIDS</small><small id="bid-val" class="g-pos">—</small>
        </div>
        <div class="progress mb-2">
          <div class="progress-bar bg-success" id="bid-bar" style="width:50%"></div>
        </div>
        <div class="d-flex justify-content-between mb-1">
          <small class="g-neg">ASKS</small><small id="ask-val" class="g-neg">—</small>
        </div>
        <div class="progress mb-3">
          <div class="progress-bar bg-danger" id="ask-bar" style="width:50%"></div>
        </div>
        <div class="d-flex justify-content-between">
          <span class="stat-label">$11 order price impact</span>
          <span class="fw-bold" id="impact-val">—</span>
        </div>
        <div class="d-flex justify-content-between mt-1">
          <span class="stat-label">Bid / Ask imbalance</span>
          <span class="g-dim" id="imbalance-val" style="font-size:.78rem">—</span>
        </div>
      </div>
    </div>
  </div>

</div><!-- /row -->

<!-- ROW 2: Chart + Trades -->
<div class="row g-3 mt-0">
  <div class="col-md-8">
    <div class="card">
      <div class="card-header fw-bold">BTC/USDT — PRICE (<span id="tf-label">1h</span>)</div>
      <div class="card-body" style="height:190px;padding:.75rem">
        <canvas id="priceChart"></canvas>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card" style="height:100%">
      <div class="card-header fw-bold">RECENT TRADES</div>
      <div style="max-height:228px;overflow-y:auto">
        <table class="table table-sm table-dark table-trades mb-0">
          <thead style="position:sticky;top:0;background:#21262d">
            <tr><th>Entered</th><th>Side</th><th>Entry</th><th>PnL</th></tr>
          </thead>
          <tbody id="trades-body">
            <tr><td colspan="4" class="text-center g-dim py-3">No trades yet</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

</div><!-- /container -->

<!-- FOOTER -->
<div class="footer-bar d-flex flex-wrap gap-3">
  <span>CPU: <b id="cpu">—</b></span>
  <span>│</span>
  <span>RAM: <b id="ram">—</b></span>
  <span>│</span>
  <span>Dashboard up: <b id="uptime">—</b></span>
  <span>│</span>
  <span>Next refresh: <b id="countdown2">30s</b></span>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
// ── Chart ───────────────────────────────────────────────────────────────────
const chart = new Chart(document.getElementById('priceChart').getContext('2d'), {
  type: 'line',
  data: { labels:[], datasets:[{ data:[], borderColor:'#58a6ff',
    backgroundColor:'rgba(88,166,255,.07)', borderWidth:2, fill:true,
    tension:.35, pointRadius:0 }]},
  options: {
    responsive:true, maintainAspectRatio:false,
    plugins:{ legend:{display:false}, tooltip:{
      callbacks:{ label: ctx => '$' + ctx.parsed.y.toLocaleString() }
    }},
    scales:{
      x:{ display:false },
      y:{ grid:{color:'#21262d'}, ticks:{color:'#8b949e',
          callback: v => '$' + Math.round(v/1000) + 'k' }}
    }, animation:{duration:300}
  }
});

// ── Countdown ───────────────────────────────────────────────────────────────
let secsLeft = 30;
setInterval(() => {
  secsLeft = Math.max(0, secsLeft - 1);
  const t = secsLeft + 's';
  document.getElementById('countdown').textContent  = '⟳ ' + t;
  document.getElementById('countdown2').textContent = t;
}, 1000);

// ── DOM helpers ─────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function heatRow(label, pct, valueStr) {
  pct = Math.max(0, Math.min(100, pct));
  const c = pct >= 100 ? '#f85149' : pct >= 80 ? '#e3b341' : pct >= 45 ? '#58a6ff' : '#3fb950';
  return `<div class="mb-3">
    <div class="d-flex justify-content-between mb-1">
      <span class="heat-label">${label}</span>
      <span class="heat-value" style="color:${c}">${valueStr}</span>
    </div>
    <div class="progress">
      <div class="progress-bar" style="width:${pct}%;background:${c}"></div>
    </div></div>`;
}

function checkRow(label, ok, detail) {
  return `<div class="mb-2 d-flex align-items-start gap-2">
    <span style="font-size:.9rem">${ok ? '✅' : '❌'}</span>
    <div><div style="font-size:.78rem;font-weight:600">${label}</div>
    <div style="font-size:.7rem;color:#8b949e">${detail}</div></div></div>`;
}

function agentCard(ok, label, detail) {
  const bg = ok ? '#1a4a2a' : '#1a1a2a';
  const bc = ok ? '#3fb950' : '#30363d';
  return `<div class="col-6 mb-1">
    <div class="d-flex align-items-center gap-1 p-1 rounded" style="background:${bg};border:1px solid ${bc}">
      <span style="font-size:.85rem">${ok ? '✅' : '❌'}</span>
      <div><div style="font-size:.75rem;font-weight:600">${label}</div>
      <div style="font-size:.68rem;color:#8b949e">${detail}</div></div>
    </div></div>`;
}

function hmmCard(regime, conf, fallback) {
  const cols = { crash:'#8b0000', bear:'#cd5c5c', neutral:'#4a5568', bull:'#2d6a4f', euphoria:'#f6c90e' };
  const icons = { crash:'🔴', bear:'🟠', neutral:'⚪', bull:'🟢', euphoria:'🟡' };
  const r   = regime || '';
  const col = cols[r]  || '#30363d';
  const ico = icons[r] || '❔';
  const blocked = r === 'crash' || r === 'bear';
  const detail  = fallback ? 'ADX fallback' : `conf ${(conf * 100).toFixed(0)}%` + (r === 'euphoria' ? ' · ½ size' : '');
  return `<div class="col-6 mb-1">
    <div class="d-flex align-items-center gap-1 p-1 rounded" style="background:${col}22;border:1px solid ${col}">
      <span style="font-size:.85rem">${blocked ? '🚫' : (r === 'euphoria' ? '⚠️' : '✅')}</span>
      <div><div style="font-size:.75rem;font-weight:600;color:${col}">${ico} HMM ${r ? r.toUpperCase() : '—'}</div>
      <div style="font-size:.68rem;color:#8b949e">${detail}</div></div>
    </div></div>`;
}

// ── Main render ─────────────────────────────────────────────────────────────
function render(d) {
  // Price header
  const up = d.price_change >= 0;
  $('price').textContent = '$' + d.price.toLocaleString('en', {minimumFractionDigits:2, maximumFractionDigits:2});
  $('price-change').innerHTML =
    `<span class="${up?'g-pos':'g-neg'}">${up?'▲':'▼'} ${Math.abs(d.price_change).toFixed(2)}%</span>`;
  const rc = d.regime === 'trending' ? '#e3b341' : '#58a6ff';
  // Under trend_filter the regime/ADX/HMM badges describe the LEGACY engine —
  // the live strategy has no regime, ADX or HMM. Label them so the most prominent
  // items on the page can't be mistaken for what is actually driving trades.
  if (d.strategy === 'trend_filter') {
    const lg = $('legacy-tag');
    if (lg) lg.textContent = 'legacy';
  }
  $('regime-badge').innerHTML =
    `<span class="badge" style="background:${rc}22;color:${rc};border:1px solid ${rc}">${d.regime.toUpperCase()}</span>`;
  $('adx-val').textContent = 'ADX ' + d.adx.toFixed(1);
  // HMM header badge
  const hmmCols = { crash:'#8b0000', bear:'#cd5c5c', neutral:'#4a5568', bull:'#2d6a4f', euphoria:'#f6c90e' };
  const hc = hmmCols[d.hmm_regime] || '#30363d';
  $('hmm-header-badge').innerHTML = d.hmm_regime
    ? `<span style="background:${hc}22;color:${hc};border:1px solid ${hc};border-radius:4px;padding:1px 6px">${d.hmm_regime.toUpperCase()} ${d.hmm_fallback ? '(ADX)' : (d.hmm_confidence*100).toFixed(0)+'%'}</span>`
    : '';
  $('last-updated').textContent = 'Updated ' + d.last_updated;
  $('error-msg').textContent = d.error || '';

  // Strategy banner — reflect what the bot ACTUALLY trades on
  const isTrend = d.strategy === 'trend_filter';
  $('strategy-name').textContent = isTrend
    ? ('TREND FILTER · ' + d.trend_sma_period + 'd SMA') : (d.strategy || 'consensus').toUpperCase();
  $('strategy-name').className = 'badge ' + (isTrend ? 'bg-success' : 'bg-secondary');
  if (isTrend) {
    const long = d.trend_position === 'long';
    const wantLong = d.trend_want_long;
    const col = long ? '#3fb950' : '#8b949e';
    const GRN = '#3fb950', RED = '#f85149';
    const pct = (v) => (v >= 0 ? '+' : '') + v.toFixed(1) + '%';
    const tint = (v, txt) => `<span style="color:${v >= 0 ? GRN : RED};font-weight:600">${txt}</span>`;

    // Above the 150d line is the bullish side of this strategy, below is bearish —
    // colour it so direction reads at a glance.
    const gapHtml = tint(d.trend_gap_pct, '(' + pct(d.trend_gap_pct) + ')');

    // Build the whole banner as ONE innerHTML assignment. Appending with
    // `textContent +=` afterwards strips every tag already set, which silently
    // flattened the colours and the bold signal.
    let html =
      `<span style="color:${col};font-weight:700">${long ? '● HOLDING BTC' : '○ IN CASH'}</span>` +
      ` &nbsp; close $${Math.round(d.trend_close).toLocaleString()}` +
      ` vs SMA${d.trend_sma_period} $${Math.round(d.trend_sma).toLocaleString()} ${gapHtml}` +
      ` &nbsp; signal: <b>${wantLong ? 'LONG' : 'FLAT'}</b>` +
      (long !== wantLong ? ' <span style="color:#e3b341">(flips next daily close)</span>' : '');

    if (long && d.position_entry) {
      html += ` &nbsp;·&nbsp; entry $${Math.round(d.position_entry).toLocaleString()}` +
              ` &nbsp;·&nbsp; ` + tint(d.unrealized_pct || 0, pct(d.unrealized_pct || 0));
    }
    $('trend-state').innerHTML = html;
    $('trend-note').textContent = 'Header regime/ADX/HMM and the Signal Heat / agent panels are LEGACY consensus telemetry — not driving trades.';
  } else {
    $('trend-state').textContent = '';
    $('trend-note').textContent = '';
  }

  // Heat
  const isRanging = d.regime === 'ranging';
  $('regime-heat-badge').textContent  = isRanging ? 'RANGING' : 'TRENDING';
  $('regime-heat-badge').style.color  = isRanging ? '#58a6ff' : '#e3b341';
  $('regime-heat-badge').style.background = isRanging ? '#58a6ff22' : '#e3b34122';

  // HMM regime section at top of heat card
  let heat = '';
  if (d.hmm_regime) {
    const hcol  = hmmCols[d.hmm_regime] || '#30363d';
    const confPct = d.hmm_fallback ? 0 : Math.round(d.hmm_confidence * 100);
    const blocked = d.hmm_regime === 'crash' || d.hmm_regime === 'bear';
    const hmmNote = blocked ? '🚫 No new entries — force exit longs'
                  : d.hmm_regime === 'euphoria' ? '⚠️ Parabolic move — position size halved'
                  : d.hmm_fallback ? 'ADX fallback (confidence too low)'
                  : '✅ Entries permitted';
    heat += `<div class="mb-3 p-2 rounded" style="background:${hcol}18;border:1px solid ${hcol}55">
      <div class="d-flex justify-content-between align-items-center">
        <span style="font-size:.8rem;font-weight:700;color:${hcol}">HMM: ${d.hmm_regime.toUpperCase()}</span>
        <span style="font-size:.7rem;color:#8b949e">${d.hmm_fallback ? 'ADX fallback' : 'conf ' + confPct + '%'}</span>
      </div>
      <div class="progress mt-1" style="height:3px;background:#21262d">
        <div style="width:${confPct}%;height:3px;background:${hcol};border-radius:2px"></div>
      </div>
      <div style="font-size:.68rem;color:#8b949e;margin-top:4px">${hmmNote}</div>
    </div>`;
  }
  if (isRanging) {
    const rsiPct = Math.max(0, (50 - d.rsi) / (50 - d.rsi_threshold) * 100);
    heat += heatRow('RSI → ' + d.rsi_threshold + ' (falling)', rsiPct, d.rsi.toFixed(1));
    const bbDist = d.price - d.bb_lower;
    const bbPct  = Math.max(0, 100 - (bbDist / (d.price * 0.025) * 100));
    heat += heatRow('Price vs BB lower', bbPct, '$' + bbDist.toFixed(0) + ' above');
    heat += checkRow('Above EMA200', d.price > d.ema200, '$' + (d.price - d.ema200).toFixed(0));
  } else {
    const rsiPct = Math.max(0, (d.rsi - 50) / (d.rsi_threshold - 50) * 100);
    heat += heatRow('RSI → ' + d.rsi_threshold + ' (rising)', rsiPct, d.rsi.toFixed(1));
    const emaStack = d.ema20 > d.ema50 && d.ema50 > d.ema200;
    heat += checkRow('EMA stack 20>50>200', emaStack,
      '20:' + Math.round(d.ema20) + '  50:' + Math.round(d.ema50));
    heat += checkRow('MACD crossover', d.macd_cross_up,
      'hist ' + (d.macd_hist >= 0 ? '+' : '') + d.macd_hist.toFixed(1));
  }
  const volPct = Math.min(110, d.vol_ratio / d.vol_threshold * 100);
  heat += heatRow('Volume spike >' + d.vol_threshold + 'x', volPct, d.vol_ratio.toFixed(2) + 'x');
  const adxPct = Math.min(110, d.adx / d.adx_threshold * 100);
  heat += heatRow('ADX → ' + d.adx_threshold, adxPct, d.adx.toFixed(1));
  heat += checkRow((d.htf||'4h') + ' Trend (EMA20>50)', d.ema20_4h > d.ema50_4h,
    d.ema20_4h > d.ema50_4h ? 'Bullish ✔' : 'Bearish ✘');
  $('heat-body').innerHTML = heat;

  // Agents
  const volOk   = d.vol_ratio >= d.vol_threshold;
  const mtfOk   = d.ema20_4h  > d.ema50_4h;
  const riskOk  = d.drawdown_pct < d.drawdown_threshold;
  let techOk;
  if (isRanging) {
    techOk = d.rsi < d.rsi_threshold && d.price < d.bb_lower && d.price > d.ema200;
  } else {
    techOk = d.rsi > d.rsi_threshold && d.ema20 > d.ema50 && d.ema50 > d.ema200 && d.macd_cross_up;
  }
  $('agents-body').innerHTML =
    agentCard(techOk, 'Technical',  isRanging ? 'RSI+BB+EMA200' : 'RSI+EMA+MACD') +
    agentCard(volOk,  'Volume',     d.vol_ratio.toFixed(2) + 'x (need ' + d.vol_threshold + 'x)') +
    agentCard(mtfOk,  (d.htf||'4h') + ' MTF',    mtfOk ? 'Bullish aligned' : 'Bearish — blocked') +
    agentCard(riskOk, 'Risk',       'DD=' + d.drawdown_pct.toFixed(1) + '%') +
    agentCard(d.ml_filter_trained, 'ML Filter',
      d.ml_filter_trained ? ('active — trained on ' + d.ml_filter_n + ' trades')
                          : 'off by design — no model on host; 63.2% CV vs 63.0% base rate, no edge (docs/RESEARCH.md)') +
    hmmCard(d.hmm_regime, d.hmm_confidence, d.hmm_fallback);

  // Signal orb
  const met = [techOk, volOk, mtfOk, riskOk].filter(Boolean).length;
  if (d.strategy === 'trend_filter') {
    // Show the live strategy's actual state. "1 / 4 conditions met" is a consensus
    // count and reads as though it gates the trade — it does not.
    const holding = d.trend_position === 'long';
    $('signal-orb').textContent = holding ? '🟢' : '○';
    $('signal-text').textContent = holding ? 'HOLDING BTC' : 'IN CASH';
    const gap = (d.trend_gap_pct === undefined) ? null : d.trend_gap_pct;
    $('conds-met').textContent = (gap === null)
      ? 'trend filter'
      : (gap >= 0 ? 'above 150d SMA (+' : 'below 150d SMA (') + gap.toFixed(1) + '%)';
  } else {
    $('conds-met').textContent = met + ' / 4 conditions met';
  }
  // Under trend_filter the orb was already set above to HOLDING/CASH. This
  // consensus block ran unconditionally afterwards and overwrote it with
  // "2/4 WARMING UP" — a count of conditions that gate nothing.
  if (d.strategy === 'trend_filter') {
    const holdingNow = d.trend_position === 'long';
    $('signal-orb').className   = 'orb ' + (holdingNow ? 'orb-go' : 'orb-wait') + ' mb-2';
    $('signal-text').style.color = holdingNow ? '#3fb950' : '#8b949e';
  } else if (met === 4) {
    $('signal-orb').className  = 'orb orb-go mb-2';
    $('signal-orb').textContent = '🔥';
    $('signal-text').textContent = 'SIGNAL POSSIBLE';
    $('signal-text').style.color = '#3fb950';
  } else if (met >= 2) {
    $('signal-orb').className  = 'orb orb-part mb-2';
    $('signal-orb').textContent = met + '/4';
    $('signal-text').textContent = 'WARMING UP';
    $('signal-text').style.color = '#e3b341';
  } else {
    $('signal-orb').className  = 'orb orb-wait mb-2';
    $('signal-orb').textContent = '⏳';
    $('signal-text').textContent = 'WAITING';
    $('signal-text').style.color = '#8b949e';
  }

  // Account
  $('balance').textContent     = '$' + d.balance.toFixed(2);
  // Equity marks the OPEN position to market. Cash alone reads unchanged for
  // months while this strategy holds, which looks like a stalled bot.
  const eq = (d.equity === undefined) ? d.balance : d.equity;
  $('equity').textContent = '$' + eq.toFixed(2);
  // NB: `up` is already declared at the top of this function for price direction.
  // Reusing it was a parse error, which killed the ENTIRE script and blanked
  // every field on the page — not just this one.
  const unrl = d.unrealized_pnl || 0, unrlPct = d.unrealized_pct || 0;
  const uel = $('unrealized');
  if (d.trend_position === 'long' && d.position_size) {
    uel.textContent = (unrl >= 0 ? '+$' : '-$') + Math.abs(unrl).toFixed(2)
                    + '  (' + (unrlPct >= 0 ? '+' : '') + unrlPct.toFixed(1) + '%)';
    uel.style.color = unrl >= 0 ? '#3fb950' : '#f85149';
  } else {
    uel.textContent = '—';
    uel.style.color = '';
  }
  $('peak').textContent        = '$' + d.peak.toFixed(2);
  $('drawdown').innerHTML      = `<span style="color:${d.drawdown_pct>10?'#f85149':'#3fb950'}">${d.drawdown_pct.toFixed(2)}%</span>`;
  $('daily-pnl').innerHTML     = `<span style="color:${d.daily_pnl>=0?'#3fb950':'#f85149'}">${d.daily_pnl>=0?'+':''}$${Math.abs(d.daily_pnl).toFixed(4)}</span>`;
  // MAX_TRADES_PER_DAY only gates the consensus engine. trend_filter trades ~2x
  // a year, so showing "0 / 5" implies a limit that does not apply to it.
  $('trades-today').textContent  = (d.strategy === 'trend_filter')
    ? d.trades_today + '  (no daily cap)'
    : d.trades_today + ' / ' + d.max_trades_per_day;
  { const tl = $('tf-label'); if (tl) tl.textContent = d.chart_timeframe || d.timeframe; }
  $('total-trades').textContent  = d.total_trades;
  $('win-rate').textContent      = d.total_trades > 0 ? d.win_rate + '%' : '—';
  $('profit-factor').textContent = d.total_trades > 0 ? d.profit_factor : '—';
  $('best-trade').textContent    = d.total_trades > 0 ? (d.best_trade >= 0 ? '+$' : '-$') + Math.abs(d.best_trade).toFixed(4)  : '—';
  $('worst-trade').textContent   = d.total_trades > 0 ? (d.worst_trade >= 0 ? '+$' : '-$') + Math.abs(d.worst_trade).toFixed(4) : '—';

  // Order book
  const tot = d.bid_depth_usdt + d.ask_depth_usdt;
  const bPct = tot > 0 ? d.bid_depth_usdt / tot * 100 : 50;
  const aPct = tot > 0 ? d.ask_depth_usdt / tot * 100 : 50;
  $('bid-bar').style.width = bPct + '%';
  $('ask-bar').style.width = aPct + '%';
  $('bid-val').textContent  = tot > 0 ? '$' + d.bid_depth_usdt.toLocaleString() : '—';
  $('ask-val').textContent  = tot > 0 ? '$' + d.ask_depth_usdt.toLocaleString() : '—';
  const ic = d.price_impact_pct > 0.05 ? '#f85149' : '#3fb950';
  $('impact-val').innerHTML = `<span style="color:${ic}">${d.price_impact_pct.toFixed(4)}%</span>`;
  $('depth-badge').textContent      = d.depth_ok ? '✔ LIQUID' : '⚠ THIN';
  $('depth-badge').style.color      = d.depth_ok ? '#3fb950' : '#f85149';
  $('depth-badge').style.background = d.depth_ok ? '#1a4a2a'  : '#4a1a1a';
  const imb = tot > 0 ? ((d.bid_depth_usdt - d.ask_depth_usdt) / tot * 100).toFixed(1) : '—';
  $('imbalance-val').textContent = tot > 0 ? (imb > 0 ? '+' : '') + imb + '% bid-heavy' : '—';

  // Chart
  const hist = d.price_history;
  chart.data.labels = hist.map((_, i) => (i - hist.length + 1) + 'h');
  chart.data.datasets[0].data = hist;
  const trending_up = hist[hist.length-1] >= hist[0];
  chart.data.datasets[0].borderColor      = trending_up ? '#3fb950' : '#f85149';
  chart.data.datasets[0].backgroundColor  = trending_up ? 'rgba(63,185,80,.07)' : 'rgba(248,81,73,.07)';
  chart.update('none');

  // Trades table
  let tbody = '';
  if (!d.recent_trades.length) {
    tbody = '<tr><td colspan="4" class="text-center g-dim py-3">No trades yet</td></tr>';
  } else {
    d.recent_trades.forEach(t => {
      const pnl = parseFloat(t.pnl_usdt || 0);
      const c = pnl >= 0 ? '#3fb950' : '#f85149';
      tbody += `<tr>
        <td>${(t.entered_at||t.timestamp||'').substring(5,10)}</td>
        <td>${t.signal||''}</td>
        <td>$${parseFloat(t.entry_price||0).toLocaleString('en',{maximumFractionDigits:0})}</td>
        <td style="color:${c}">${pnl>=0?'+':''}${pnl.toFixed(4)}</td>
      </tr>`;
    });
  }
  $('trades-body').innerHTML = tbody;

  // Footer
  $('cpu').textContent    = d.cpu_pct + '%';
  $('ram').textContent    = d.ram_used_mb + ' / ' + d.ram_total_mb + ' MB';
  $('uptime').textContent = d.uptime;
}

// ── Poll ─────────────────────────────────────────────────────────────────────
function poll() {
  fetch('/api/data')
    .then(r => r.json())
    .then(d => { render(d); secsLeft = 30; $('pulse-dot').style.background = '#3fb950'; })
    .catch(e => {
      $('error-msg').textContent = '⚠ ' + e;
      $('pulse-dot').style.background = '#f85149';
    });
}

poll();
setInterval(poll, 30000);
</script>
</body>
</html>"""


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
@_require_auth
def index():
    return HTML

@app.route("/api/data")
@_require_auth
def api_data():
    return jsonify(fetch_data())


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Dashboard running → http://localhost:5000")
    print("From your browser: http://<your-oracle-ip>:5000  (after opening port in Oracle VCN)")
    # 0.0.0.0 = reachable from your laptop when running on Oracle
    app.run(host="0.0.0.0", port=5000, debug=False)

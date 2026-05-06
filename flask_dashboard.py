"""
flask_dashboard.py — Browser-based dashboard for Crypto Survival System.

Run alongside bot.py in a separate tmux window:
    python flask_dashboard.py

Then open in your browser: http://<oracle-ip>:5000
(Oracle: open port 5000 in VCN security list + sudo firewall-cmd --add-port=5000/tcp --permanent)
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd
import psutil
from flask import Flask, jsonify

import config
from strategy import RegimeDetector

app = Flask(__name__)
_start_time = time.monotonic()
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
        "rsi_threshold": config.RSI_TREND_BUY_MIN,
        "adx_threshold": config.ADX_TREND_THRESHOLD,
        "vol_threshold": config.VOLUME_SPIKE_MIN,
        "balance": config.STARTING_CAPITAL, "peak": config.STARTING_CAPITAL,
        "drawdown_pct": 0, "daily_pnl": 0,
        "trades_today": 0, "total_trades": 0,
        "win_trades": 0, "loss_trades": 0,
        "win_rate": 0, "profit_factor": 0,
        "best_trade": 0, "worst_trade": 0,
        "recent_trades": [],
        "price_history": [],
        "bid_depth_usdt": 0, "ask_depth_usdt": 0,
        "price_impact_pct": 0, "depth_ok": True,
        "cpu_pct": 0, "ram_used_mb": 0, "ram_total_mb": 0,
        "last_updated": "—", "uptime": "00:00:00", "error": "",
    }

    try:
        exchange = _build_exchange()
        symbol   = config.TRADING_PAIR

        # ── 1h OHLCV ──────────────────────────────────────────────────────────
        ohlcv = exchange.fetch_ohlcv(symbol, "1h", limit=300)
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

        d["rsi_threshold"] = (
            config.RSI_RANGE_BUY_MAX if d["regime"] == "ranging"
            else config.RSI_TREND_BUY_MIN
        )

        # ── 4h OHLCV ──────────────────────────────────────────────────────────
        ohlcv_4h = exchange.fetch_ohlcv(symbol, "4h", limit=100)
        df4      = pd.DataFrame(ohlcv_4h, columns=["ts","open","high","low","close","volume"])
        c4       = df4["close"]
        d["ema20_4h"] = float(c4.ewm(span=20, adjust=False).mean().iloc[-1])
        d["ema50_4h"] = float(c4.ewm(span=50, adjust=False).mean().iloc[-1])

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
            conn   = sqlite3.connect(config.DB_PATH)
            trades = pd.read_sql("SELECT * FROM trades ORDER BY id DESC LIMIT 100", conn)
            conn.close()

            if not trades.empty:
                d["total_trades"]  = len(trades)
                d["recent_trades"] = trades.head(10).to_dict("records")
                today   = datetime.now(timezone.utc).date().isoformat()
                today_t = trades[trades["timestamp"].str.startswith(today)]
                d["trades_today"] = len(today_t)
                d["daily_pnl"]    = float(today_t["pnl_usdt"].sum()) if not today_t.empty else 0.0
                d["balance"]      = config.STARTING_CAPITAL + float(trades["pnl_usdt"].sum())
                d["peak"]         = max(config.STARTING_CAPITAL, d["balance"])
                d["drawdown_pct"] = max(0.0, (d["peak"] - d["balance"]) / d["peak"] * 100)

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
  <span class="ms-auto d-flex align-items-center gap-2">
    <span class="pulse-dot" id="pulse-dot"></span>
    <span class="g-dim" id="last-updated" style="font-size:.78rem">—</span>
    <span class="g-dim" id="countdown" style="font-size:.78rem"></span>
  </span>
  <span class="text-danger" id="error-msg" style="font-size:.75rem"></span>
</div>

<div class="container-fluid p-3">
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
          <div class="col-6"><div class="stat-label">Balance</div><div class="stat-value" id="balance">$—</div></div>
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
      <div class="card-header fw-bold">BTC/USDT — 48H PRICE</div>
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
            <tr><th>Date</th><th>Side</th><th>Entry</th><th>PnL</th></tr>
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

// ── Main render ─────────────────────────────────────────────────────────────
function render(d) {
  // Price header
  const up = d.price_change >= 0;
  $('price').textContent = '$' + d.price.toLocaleString('en', {minimumFractionDigits:2, maximumFractionDigits:2});
  $('price-change').innerHTML =
    `<span class="${up?'g-pos':'g-neg'}">${up?'▲':'▼'} ${Math.abs(d.price_change).toFixed(2)}%</span>`;
  const rc = d.regime === 'trending' ? '#e3b341' : '#58a6ff';
  $('regime-badge').innerHTML =
    `<span class="badge" style="background:${rc}22;color:${rc};border:1px solid ${rc}">${d.regime.toUpperCase()}</span>`;
  $('adx-val').textContent = 'ADX ' + d.adx.toFixed(1);
  $('last-updated').textContent = 'Updated ' + d.last_updated;
  $('error-msg').textContent = d.error || '';

  // Heat
  const isRanging = d.regime === 'ranging';
  $('regime-heat-badge').textContent  = isRanging ? 'RANGING' : 'TRENDING';
  $('regime-heat-badge').style.color  = isRanging ? '#58a6ff' : '#e3b341';
  $('regime-heat-badge').style.background = isRanging ? '#58a6ff22' : '#e3b34122';

  let heat = '';
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
  heat += checkRow('4h Trend (EMA20>50)', d.ema20_4h > d.ema50_4h,
    d.ema20_4h > d.ema50_4h ? 'Bullish ✔' : 'Bearish ✘');
  $('heat-body').innerHTML = heat;

  // Agents
  const volOk   = d.vol_ratio >= d.vol_threshold;
  const mtfOk   = d.ema20_4h  > d.ema50_4h;
  const riskOk  = d.drawdown_pct < 25;
  let techOk;
  if (isRanging) {
    techOk = d.rsi < d.rsi_threshold && d.price < d.bb_lower && d.price > d.ema200;
  } else {
    techOk = d.rsi > d.rsi_threshold && d.ema20 > d.ema50 && d.ema50 > d.ema200 && d.macd_cross_up;
  }
  $('agents-body').innerHTML =
    agentCard(techOk, 'Technical',  isRanging ? 'RSI+BB+EMA200' : 'RSI+EMA+MACD') +
    agentCard(volOk,  'Volume',     d.vol_ratio.toFixed(2) + 'x (need ' + d.vol_threshold + 'x)') +
    agentCard(mtfOk,  '4h MTF',    mtfOk ? 'Bullish aligned' : 'Bearish — blocked') +
    agentCard(riskOk, 'Risk',       'DD=' + d.drawdown_pct.toFixed(1) + '%') +
    agentCard(false,  'ML Filter',  '⚪ bypass (<200 trades)');

  // Signal orb
  const met = [techOk, volOk, mtfOk, riskOk].filter(Boolean).length;
  $('conds-met').textContent = met + ' / 4 conditions met';
  if (met === 4) {
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
  $('peak').textContent        = '$' + d.peak.toFixed(2);
  $('drawdown').innerHTML      = `<span style="color:${d.drawdown_pct>10?'#f85149':'#3fb950'}">${d.drawdown_pct.toFixed(2)}%</span>`;
  $('daily-pnl').innerHTML     = `<span style="color:${d.daily_pnl>=0?'#3fb950':'#f85149'}">${d.daily_pnl>=0?'+':''}$${Math.abs(d.daily_pnl).toFixed(4)}</span>`;
  $('trades-today').textContent  = d.trades_today + ' / 2';
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
        <td>${(t.timestamp||'').substring(5,10)}</td>
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
def index():
    return HTML

@app.route("/api/data")
def api_data():
    return jsonify(fetch_data())


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Dashboard running → http://localhost:5000")
    print("From your browser: http://64.181.218.172:5000  (after opening port in Oracle VCN)")
    # 0.0.0.0 = reachable from your laptop when running on Oracle
    app.run(host="0.0.0.0", port=5000, debug=False)

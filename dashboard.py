"""
dashboard.py — Real-time terminal dashboard for the trading bot.

Run in a separate terminal alongside bot.py:
    python dashboard.py

Read-only: does NOT interfere with the running bot.
Refreshes every 30 seconds (matches bot tick interval).
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import pandas as pd
import psutil
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config
from strategy import RegimeDetector

console = Console()
_start_time = time.monotonic()
REFRESH_SECONDS = 30


# ─── Data container ───────────────────────────────────────────────────────────

@dataclass
class DashboardData:
    # Price
    price:        float = 0.0
    price_change: float = 0.0   # % vs 24h ago

    # Indicators
    rsi:          float = 0.0
    adx:          float = 0.0
    macd_hist:    float = 0.0
    macd_cross_up: bool = False
    ema20:        float = 0.0
    ema50:        float = 0.0
    ema200:       float = 0.0
    bb_lower:     float = 0.0
    bb_upper:     float = 0.0
    vol_ratio:    float = 0.0   # current / 50-bar avg
    regime:       str   = "unknown"
    plus_di:      float = 0.0
    minus_di:     float = 0.0

    # 4h
    ema20_4h:     float = 0.0
    ema50_4h:     float = 0.0

    # Account (from DB)
    balance:      float = config.STARTING_CAPITAL
    peak:         float = config.STARTING_CAPITAL
    drawdown_pct: float = 0.0
    daily_pnl:    float = 0.0
    trades_today: int   = 0
    total_trades: int   = 0

    # Recent trades
    recent_trades: list[dict] = field(default_factory=list)

    # System
    cpu_pct:      float = 0.0
    ram_used_mb:  float = 0.0
    ram_total_mb: float = 0.0

    # Meta
    last_updated: str = "—"
    error:        str = ""


# ─── Data fetcher ─────────────────────────────────────────────────────────────

def _build_exchange():
    if config.EXCHANGE == "kucoin":
        return ccxt.kucoin({"enableRateLimit": True})
    return ccxt.binance({"enableRateLimit": True})


def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, 1e-10)
    return float((100 - (100 / (1 + rs))).iloc[-1])


def _bollinger(series: pd.Series, period=20, std_dev=2):
    mid   = series.rolling(period).mean()
    std   = series.rolling(period).std()
    return float((mid + std_dev * std).iloc[-1]), float((mid - std_dev * std).iloc[-1])


def fetch_data() -> DashboardData:
    d = DashboardData()
    try:
        exchange = _build_exchange()

        # ── 1h OHLCV ──────────────────────────────────────────────────────────
        ohlcv = exchange.fetch_ohlcv(config.TRADING_PAIR, "1h", limit=300)
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df = df.set_index("ts")

        close = df["close"]
        d.price = float(close.iloc[-1])
        d.price_change = (d.price - float(close.iloc[-25])) / float(close.iloc[-25]) * 100

        # Indicators
        d.rsi = _rsi(close)

        ema_fast  = close.ewm(span=12, adjust=False).mean()
        ema_slow  = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        sig_line  = macd_line.ewm(span=9, adjust=False).mean()
        hist      = macd_line - sig_line
        d.macd_hist     = float(hist.iloc[-1])
        d.macd_cross_up = (macd_line.iloc[-1] > sig_line.iloc[-1] and
                           macd_line.iloc[-2] <= sig_line.iloc[-2])

        d.ema20  = float(close.ewm(span=20,  adjust=False).mean().iloc[-1])
        d.ema50  = float(close.ewm(span=50,  adjust=False).mean().iloc[-1])
        d.ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
        d.bb_upper, d.bb_lower = _bollinger(close)

        vol_avg   = float(df["volume"].rolling(50).mean().iloc[-1])
        d.vol_ratio = float(df["volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 0.0

        regime_info = RegimeDetector().detect(df)
        d.regime   = regime_info["regime"]
        d.adx      = regime_info["adx"]
        d.plus_di  = regime_info["plus_di"]
        d.minus_di = regime_info["minus_di"]

        # ── 4h OHLCV ──────────────────────────────────────────────────────────
        ohlcv_4h = exchange.fetch_ohlcv(config.TRADING_PAIR, "4h", limit=100)
        df4 = pd.DataFrame(ohlcv_4h, columns=["ts","open","high","low","close","volume"])
        close4 = df4["close"]
        d.ema20_4h = float(close4.ewm(span=20, adjust=False).mean().iloc[-1])
        d.ema50_4h = float(close4.ewm(span=50, adjust=False).mean().iloc[-1])

        # ── Database ──────────────────────────────────────────────────────────
        if Path(config.DB_PATH).exists():
            conn = sqlite3.connect(config.DB_PATH)
            trades = pd.read_sql(
                "SELECT * FROM trades ORDER BY id DESC LIMIT 10", conn
            )
            decisions = pd.read_sql(
                "SELECT * FROM decisions ORDER BY id DESC LIMIT 1", conn
            )
            conn.close()

            if not trades.empty:
                d.total_trades = len(trades)
                d.recent_trades = trades.head(3).to_dict("records")
                today = datetime.now(timezone.utc).date().isoformat()
                today_trades = trades[trades["timestamp"].str.startswith(today)]
                d.trades_today = len(today_trades)
                d.daily_pnl    = float(today_trades["pnl_usdt"].sum()) if not today_trades.empty else 0.0

                # Reconstruct balance from starting capital + all PnL
                d.balance  = config.STARTING_CAPITAL + float(trades["pnl_usdt"].sum())
                d.peak     = max(config.STARTING_CAPITAL, d.balance)
                d.drawdown_pct = max(0.0, (d.peak - d.balance) / d.peak * 100)

        # ── System ────────────────────────────────────────────────────────────
        d.cpu_pct     = psutil.cpu_percent(interval=0.1)
        mem           = psutil.virtual_memory()
        d.ram_used_mb = mem.used / 1024 / 1024
        d.ram_total_mb = mem.total / 1024 / 1024

        d.last_updated = datetime.now().strftime("%H:%M:%S")

    except Exception as e:
        d.error = str(e)

    return d


# ─── Heat helpers ─────────────────────────────────────────────────────────────

def _heat_bar(pct: float, width: int = 20) -> Text:
    """Returns a coloured progress bar string."""
    pct = max(0.0, min(100.0, pct))
    filled = int(width * pct / 100)
    bar    = "█" * filled + "░" * (width - filled)

    if pct >= 100:
        style = "bold bright_red"
    elif pct >= 80:
        style = "red"
    elif pct >= 60:
        style = "yellow"
    elif pct >= 40:
        style = "green"
    else:
        style = "dim"

    t = Text()
    t.append(f"[{bar}] ", style=style)
    t.append(f"{pct:5.1f}%", style=style)
    return t


def _check(condition: bool) -> Text:
    t = Text()
    if condition:
        t.append("✅", style="green")
    else:
        t.append("❌", style="red")
    return t


# ─── Panel builders ───────────────────────────────────────────────────────────

def _header(d: DashboardData) -> Text:
    arrow  = "▲" if d.price_change >= 0 else "▼"
    color  = "green" if d.price_change >= 0 else "red"
    regime_color = "yellow" if d.regime == "trending" else "cyan"

    t = Text()
    t.append("  CRYPTO SURVIVAL SYSTEM  ", style="bold white on dark_blue")
    t.append("  ")
    t.append(f"BTC/USDT  ${d.price:,.2f}  ", style="bold white")
    t.append(f"{arrow} {d.price_change:+.2f}%", style=f"bold {color}")
    t.append("    Regime: ", style="dim")
    t.append(d.regime.upper(), style=f"bold {regime_color}")
    t.append(f"  ADX {d.adx:.1f}", style="dim")
    if d.error:
        t.append(f"  ⚠ {d.error[:60]}", style="bold red")
    return t


def _account_panel(d: DashboardData) -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column(style="bold white")

    dd_color = "red" if d.drawdown_pct > 10 else "green"
    pnl_color = "green" if d.daily_pnl >= 0 else "red"

    t.add_row("Balance",   f"${d.balance:.2f}")
    t.add_row("Peak",      f"${d.peak:.2f}")
    t.add_row("Drawdown",  Text(f"{d.drawdown_pct:.2f}%", style=dd_color))
    t.add_row("PnL Today", Text(f"${d.daily_pnl:+.4f}", style=pnl_color))
    t.add_row("Trades",    f"{d.trades_today}/2 today  ({d.total_trades} total)")

    return Panel(t, title="[bold]ACCOUNT", border_style="blue", box=box.ROUNDED)


def _heat_panel(d: DashboardData) -> Panel:
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(width=18, style="dim")
    tbl.add_column(width=28)
    tbl.add_column(width=8, style="dim")

    def row(label, pct, value_str):
        tbl.add_row(label, _heat_bar(pct), value_str)

    if d.regime == "ranging":
        tbl.add_row(Text("── RANGING MODE ──", style="cyan bold"), Text(""), Text(""))
        # RSI needs to go DOWN to 23.7
        rsi_heat = max(0, (50 - d.rsi) / (50 - config.RSI_RANGE_BUY_MAX) * 100)
        row(f"RSI → {config.RSI_RANGE_BUY_MAX}", rsi_heat, f"{d.rsi:.1f}")

        # Price vs lower BB
        if d.bb_lower > 0:
            bb_heat = max(0, min(100, (1 - (d.price - d.bb_lower) /
                         max(0.01, d.price - d.bb_lower + 500)) * 100))
        else:
            bb_heat = 0
        row("Price vs BB low", bb_heat, f"${d.price - d.bb_lower:+.0f}")

        above_ema200 = d.price > d.ema200
        tbl.add_row("Above EMA200", _check(above_ema200),
                    f"${d.price - d.ema200:+.0f}")

    else:
        tbl.add_row(Text("── TRENDING MODE ──", style="yellow bold"), Text(""), Text(""))
        # RSI needs to go UP to 64.1
        rsi_heat = max(0, min(100, (d.rsi - 50) / (config.RSI_TREND_BUY_MIN - 50) * 100))
        row(f"RSI → {config.RSI_TREND_BUY_MIN}", rsi_heat, f"{d.rsi:.1f}")

        ema_stack = d.ema20 > d.ema50 > d.ema200
        tbl.add_row("EMA stack", _check(ema_stack), "20>50>200")

        macd_heat = max(0, min(100, (d.macd_hist + 100) / 200 * 100))
        row("MACD hist", macd_heat, f"{d.macd_hist:+.1f}")

    # Volume (shared)
    vol_heat = min(100, d.vol_ratio / config.VOLUME_SPIKE_MIN * 100)
    row(f"Volume >{config.VOLUME_SPIKE_MIN}x", vol_heat, f"{d.vol_ratio:.2f}x")

    # ADX
    adx_heat = min(100, d.adx / config.ADX_TREND_THRESHOLD * 100)
    row(f"ADX → {config.ADX_TREND_THRESHOLD}", adx_heat, f"{d.adx:.1f}")

    # 4h alignment
    aligned_4h = d.ema20_4h > d.ema50_4h
    tbl.add_row("4h Trend", _check(aligned_4h),
                "EMA20>50" if aligned_4h else "EMA20<50")

    return Panel(tbl, title="[bold]SIGNAL HEAT", border_style="yellow", box=box.ROUNDED)


def _agents_panel(d: DashboardData) -> Panel:
    tbl = Table.grid(padding=(0, 2))
    tbl.add_column(width=14, style="dim")
    tbl.add_column(width=6)
    tbl.add_column(style="dim")

    # Technical
    if d.regime == "ranging":
        tech_ok = (d.rsi < config.RSI_RANGE_BUY_MAX and
                   d.price < d.bb_lower and d.price > d.ema200)
        tech_reason = f"RSI={d.rsi:.1f} BB={d.bb_lower:.0f}"
    else:
        tech_ok = (d.rsi > config.RSI_TREND_BUY_MIN and
                   d.ema20 > d.ema50 > d.ema200 and d.macd_cross_up)
        tech_reason = f"RSI={d.rsi:.1f} MACD={'cross' if d.macd_cross_up else 'no cross'}"

    vol_ok      = d.vol_ratio >= config.VOLUME_SPIKE_MIN
    mtf_ok      = d.ema20_4h > d.ema50_4h
    risk_ok     = d.drawdown_pct < config.MAX_DRAWDOWN_KILL_SWITCH * 100

    signal_ok   = tech_ok and vol_ok and mtf_ok
    tbl.add_row("Technical",  _check(signal_ok), tech_reason)
    tbl.add_row("Volume",     _check(vol_ok),    f"{d.vol_ratio:.2f}x (need {config.VOLUME_SPIKE_MIN}x)")
    tbl.add_row("4h MTF",     _check(mtf_ok),    "aligned" if mtf_ok else "opposed")
    tbl.add_row("Risk",       _check(risk_ok),   f"DD={d.drawdown_pct:.1f}%")
    tbl.add_row("ML Filter",  Text("⚪ bypass", style="dim"), "training (<200 trades)")

    if signal_ok and risk_ok:
        tbl.add_row("", Text(""), Text(""))
        tbl.add_row("STATUS", Text("🔥 SIGNAL POSSIBLE", style="bold bright_red"), "")
    else:
        tbl.add_row("", Text(""), Text(""))
        tbl.add_row("STATUS", Text("⏳ WAITING", style="dim"), "")

    return Panel(tbl, title="[bold]AGENTS", border_style="green", box=box.ROUNDED)


def _trades_panel(d: DashboardData) -> Panel:
    if not d.recent_trades:
        return Panel(
            Align.center(Text("No trades yet", style="dim"), vertical="middle"),
            title="[bold]RECENT TRADES", border_style="magenta", box=box.ROUNDED
        )

    tbl = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    tbl.add_column("Time",   style="dim", width=12)
    tbl.add_column("Side",   width=5)
    tbl.add_column("Entry",  width=10)
    tbl.add_column("Exit",   width=10)
    tbl.add_column("PnL",    width=10)

    for tr in d.recent_trades:
        pnl   = float(tr.get("pnl_usdt", 0))
        color = "green" if pnl >= 0 else "red"
        ts    = str(tr.get("timestamp", ""))[:10]
        tbl.add_row(
            ts,
            str(tr.get("signal", ""))[:4],
            f"${float(tr.get('entry_price', 0)):,.0f}",
            f"${float(tr.get('exit_price',  0)):,.0f}",
            Text(f"${pnl:+.4f}", style=color),
        )

    return Panel(tbl, title="[bold]RECENT TRADES", border_style="magenta", box=box.ROUNDED)


def _system_panel(d: DashboardData) -> Text:
    uptime_s = int(time.monotonic() - _start_time)
    h, r     = divmod(uptime_s, 3600)
    m, s     = divmod(r, 60)

    cpu_color = "red" if d.cpu_pct > 80 else "green"
    ram_pct   = d.ram_used_mb / d.ram_total_mb * 100 if d.ram_total_mb else 0
    ram_color = "red" if ram_pct > 85 else "green"

    t = Text()
    t.append(f"  CPU: ", style="dim")
    t.append(f"{d.cpu_pct:.0f}%", style=cpu_color)
    t.append(f"  │  RAM: ", style="dim")
    t.append(f"{d.ram_used_mb:.0f}/{d.ram_total_mb:.0f} MB", style=ram_color)
    t.append(f"  │  Dashboard up: {h:02d}:{m:02d}:{s:02d}", style="dim")
    t.append(f"  │  Updated: {d.last_updated}", style="dim")
    t.append(f"  │  Refresh: {REFRESH_SECONDS}s", style="dim")
    return t


# ─── Layout builder ───────────────────────────────────────────────────────────

def build_layout(d: DashboardData) -> Layout:
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    layout["left"].split_column(
        Layout(name="account", ratio=1),
        Layout(name="trades",  ratio=1),
    )
    layout["right"].split_column(
        Layout(name="heat",   ratio=3),
        Layout(name="agents", ratio=2),
    )

    layout["header"].update(Panel(_header(d), box=box.HEAVY, style="on dark_blue"))
    layout["account"].update(_account_panel(d))
    layout["trades"].update(_trades_panel(d))
    layout["heat"].update(_heat_panel(d))
    layout["agents"].update(_agents_panel(d))
    layout["footer"].update(Panel(_system_panel(d), box=box.ROUNDED, style="dim"))

    return layout


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    console.clear()
    console.print("[bold cyan]Loading dashboard...[/]")
    d = fetch_data()

    with Live(build_layout(d), console=console, refresh_per_second=2,
              screen=True) as live:
        while True:
            time.sleep(REFRESH_SECONDS)
            d = fetch_data()
            live.update(build_layout(d))


if __name__ == "__main__":
    main()

"""
Reads /tmp/bot_logs.txt, parses the latest decision line, and sends a Telegram report.

Handles BOTH strategies:
  [TREND] ...  trend_filter — one line per closed daily candle (LIVE since Aug 2026)
  [TICK]  ...  consensus    — one line per 60s cycle (legacy)

The trend filter logs ~1 line/day, so a report that greps only [TICK] finds nothing
and looks identical to a dead bot. Detect which format is present rather than
assuming, and say plainly when neither is.
"""
import re
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone

with open("/tmp/bot_logs.txt") as f:
    raw = f.read()

trend = re.findall(r'\[TREND\] (candle=.+)', raw)
ticks = re.findall(r'\[TICK\] (.+)', raw)
date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def g(pattern, text, idx=1, cast=str, default=None):
    m = re.search(pattern, text)
    return cast(m.group(idx)) if m else default


# ─── shared risk fields (identical suffix in both formats) ───────────────────
def risk_lines(last):
    bal   = g(r'Balance=\$([\d.]+)', last)
    pnl   = g(r'DailyPnL=\$([+-]?[\d.]+)', last)
    dd    = g(r'Drawdown=([\d.-]+)%', last)
    kill  = g(r'KillSwitch=(\w+)', last)
    trd   = re.search(r'Trades=(\d+)/(\d+)', last)
    return [
        f"Balance: ${bal or '?'} | Daily PnL: ${pnl or '0'}",
        f"Drawdown: {dd or '0'}% | Kill switch: {'ON' if kill == 'True' else 'OFF'}",
        f"Trades today: {trd.group(1)}/{trd.group(2)}" if trd else "Trades today: 0",
    ]


if trend:
    # ─── trend_filter report ─────────────────────────────────────────────────
    last    = trend[-1]
    candle  = g(r'candle=([\d-]+)', last)
    close   = g(r'close=([\d.]+)', last, cast=float)
    sma     = g(r'SMA150=([\d.]+)', last, cast=float)
    want    = g(r'-> want=(\w+)', last)
    holding = g(r'holding=(\w+)', last)

    gap = ((close / sma - 1) * 100) if (close and sma) else None
    state = "HOLDING BTC" if holding == "True" else "IN CASH"
    flip  = (want == "LONG") != (holding == "True")

    lines = [
        f"Daily Bot Report - {date_str} 7am SAST",
        "Strategy: trend_filter (150d SMA, long/flat)",
        "",
        f"Position: {state}",
        f"Last candle: {candle or '?'}",
        f"Close: ${close:,.0f} vs SMA150 ${sma:,.0f}" if close and sma else "Close: ?",
        f"Distance to SMA: {gap:+.1f}%" if gap is not None else "",
        f"Signal: want {want or '?'}" + ("  <-- FLIP PENDING" if flip else ""),
        "",
        *risk_lines(last),
        "",
        f"Decisions in window: {len(trend)} (1 per daily candle — low count is normal)",
    ]
    msg = "\n".join(l for l in lines if l != "")

elif ticks:
    # ─── legacy consensus report ─────────────────────────────────────────────
    last  = ticks[-1]
    price = g(r'price=([\d.]+)', last, cast=float)
    hmm   = re.search(r'HMM=(\w+)\(([\d.]+)\)', last)

    hmm_counts = {}
    for t in ticks:
        m = re.search(r'HMM=(\w+)\(', t)
        if m:
            hmm_counts[m.group(1)] = hmm_counts.get(m.group(1), 0) + 1
    hmm_lines = "\n".join(
        f"  {k}: {v} ({v * 100 // len(ticks)}%)"
        for k, v in sorted(hmm_counts.items(), key=lambda x: -x[1])
    ) or "  (no HMM data)"

    lines = [
        f"Daily Bot Report - {date_str} 7am SAST",
        "Strategy: consensus (legacy)",
        "",
        f"Price: ${price:,.0f}" if price else "Price: ?",
        f"Regime: {g(r'regime=(\w+)', last) or '?'}",
        f"HMM: {hmm.group(1)} ({int(float(hmm.group(2)) * 100)}%)" if hmm else "HMM: ?",
        *risk_lines(last),
        "",
        f"HMM regime (last {len(ticks)} ticks):",
        hmm_lines,
        "",
        f"Volume blocks: {raw.count('Low volume')} | HOLDs: {raw.count('signal=HOLD')}",
    ]
    msg = "\n".join(lines)

else:
    msg = (f"Daily Bot Report - {date_str}\n\n"
           "No [TREND] or [TICK] lines found in the last 2 days of logs.\n"
           "The bot may be down, or the log format changed again.")

token   = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]
url     = f"https://api.telegram.org/bot{token}/sendMessage"
data    = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
urllib.request.urlopen(url, data)
print("Sent:", msg)

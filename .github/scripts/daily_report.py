"""
Reads /tmp/bot_logs.txt, parses the latest tick, and sends a Telegram report.
"""
import re
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone

with open("/tmp/bot_logs.txt") as f:
    raw = f.read()

ticks = re.findall(r'\[TICK\] (.+)', raw)

if not ticks:
    msg = "Daily Report: No tick data found. Bot may be down."
else:
    last = ticks[-1]

    price     = re.search(r'price=([\d.]+)', last)
    regime    = re.search(r'regime=(\w+)', last)
    hmm       = re.search(r'HMM=(\w+)\(([\d.]+)\)', last)
    balance   = re.search(r'Balance=\$([\d.]+)', last)
    drawdown  = re.search(r'Drawdown=([\d.]+)%', last)
    daily_pnl = re.search(r'DailyPnL=\$([+-]?[\d.]+)', last)
    trades    = re.search(r'Trades=(\d+)/(\d+)', last)
    kill      = re.search(r'KillSwitch=(\w+)', last)

    # HMM distribution
    hmm_counts = {}
    for t in ticks:
        m = re.search(r'HMM=(\w+)\(', t)
        if m:
            label = m.group(1)
            hmm_counts[label] = hmm_counts.get(label, 0) + 1
    total_ticks = len(ticks)
    hmm_lines = "\n".join(
        f"  {k}: {v} ({v * 100 // total_ticks}%)"
        for k, v in sorted(hmm_counts.items(), key=lambda x: -x[1])
    ) or "  (no HMM data)"

    vol_blocks = raw.count("Low volume")
    holds = raw.count("signal=HOLD")
    kill_status = "ON" if kill and kill.group(1) == "True" else "OFF"

    price_val   = f"${float(price.group(1)):,.0f}" if price else "?"
    regime_val  = regime.group(1) if regime else "?"
    hmm_val     = f"{hmm.group(1)} ({int(float(hmm.group(2)) * 100)}%)" if hmm else "?"
    bal_val     = f"${balance.group(1)}" if balance else "?"
    pnl_val     = f"${daily_pnl.group(1)}" if daily_pnl else "$0"
    dd_val      = f"{drawdown.group(1)}%" if drawdown else "0%"
    trades_val  = f"{trades.group(1)}/{trades.group(2)}" if trades else "0/5"
    date_str    = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"Daily Bot Report - {date_str} 7am SAST",
        "",
        f"Price: {price_val} | Regime: {regime_val}",
        f"HMM: {hmm_val}",
        f"Balance: {bal_val} | Daily PnL: {pnl_val}",
        f"Drawdown: {dd_val} | Kill switch: {kill_status}",
        f"Trades today: {trades_val}",
        "",
        f"HMM regime (last {total_ticks} ticks):",
        hmm_lines,
        "",
        f"Volume blocks: {vol_blocks} | HOLDs: {holds}",
    ]
    msg = "\n".join(lines)

token   = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]
url     = f"https://api.telegram.org/bot{token}/sendMessage"
data    = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
urllib.request.urlopen(url, data)
print("Sent:", msg)

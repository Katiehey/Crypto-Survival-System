"""
Reads /tmp/baseline.txt and /tmp/proposed.txt backtest outputs,
compares results, and sends a Telegram proposal.
"""
import re
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone


def parse_backtest(path):
    try:
        with open(path) as f:
            text = f.read()
        sharpe = re.search(r'Sharpe Ratio:\s+([+-]?[\d.]+)', text)
        dd     = re.search(r'Max Drawdown:\s+([\d.]+)', text)
        wr     = re.search(r'Win Rate:\s+([\d.]+)', text)
        trades = re.search(r'Total Trades:\s+(\d+)', text)
        ret    = re.search(r'Total Return:\s+([+-]?[\d.]+)', text)
        return {
            "sharpe": float(sharpe.group(1)) if sharpe else 0,
            "dd":     float(dd.group(1))     if dd     else 0,
            "wr":     float(wr.group(1))     if wr     else 0,
            "trades": int(trades.group(1))   if trades else 0,
            "ret":    float(ret.group(1))    if ret    else 0,
        }
    except Exception as e:
        return {"sharpe": 0, "dd": 0, "wr": 0, "trades": 0, "ret": 0, "error": str(e)}


b = parse_backtest("/tmp/baseline.txt")
p = parse_backtest("/tmp/proposed.txt")
date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

current_vol  = os.environ.get("CURRENT_VOL",  "1.5")
proposed_vol = os.environ.get("PROPOSED_VOL", "1.3")

if p["sharpe"] < b["sharpe"] or p["dd"] > b["dd"] + 2:
    lines = [
        f"Bot Optimizer - {date}",
        "",
        "PROBLEM: Volume filter blocking most entries.",
        f"PROPOSED: VOLUME_SPIKE_MIN {current_vol} -> {proposed_vol}",
        "",
        "AUTO-REJECTED",
        f"Backtest Sharpe would drop: {b['sharpe']:.2f} -> {p['sharpe']:.2f}",
        "No change applied. Bot parameters unchanged.",
    ]
else:
    sharpe_delta = p["sharpe"] - b["sharpe"]
    assessment = (
        "Modest improvement — worth applying."
        if sharpe_delta > 0.1
        else "No meaningful improvement. Skipping recommended."
    )
    lines = [
        f"Bot Optimizer - {date}",
        "",
        "PROBLEM: Volume filter blocking most entries.",
        f"PROPOSED: VOLUME_SPIKE_MIN {current_vol} -> {proposed_vol}",
        "",
        "BACKTEST (400 days, walk-forward):",
        f"         Before   After",
        f"Sharpe:  {b['sharpe']:.2f}     {p['sharpe']:.2f}",
        f"Trades:  {b['trades']}        {p['trades']}",
        f"Max DD:  {b['dd']:.1f}%    {p['dd']:.1f}%",
        f"Win rate:{b['wr']:.1f}%    {p['wr']:.1f}%",
        f"Return:  {b['ret']:.1f}%    {p['ret']:.1f}%",
        "",
        f"ASSESSMENT: {assessment}",
        "",
        "Reply YES to apply, NO to skip.",
    ]

msg = "\n".join(lines)

token   = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]
url     = f"https://api.telegram.org/bot{token}/sendMessage"
data    = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
urllib.request.urlopen(url, data)
print("Sent:", msg)

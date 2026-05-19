"""
pulse.py — Local heartbeat monitor. Run on your Mac, not on Oracle.

Pings the Oracle server every 10 minutes.
If the server stops responding, plays an alert sound 3 times.

Usage:
    python pulse.py
    python pulse.py --ip 64.181.218.172 --interval 10
"""
from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
import time

ORACLE_IP = "64.181.218.172"
ALERT_SOUND = "/System/Library/Sounds/Basso.aiff"  # built-in macOS alert sound


def ping(ip: str) -> bool:
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "3", ip],
        capture_output=True,
    )
    return result.returncode == 0


def beep(times: int = 3):
    if sys.platform != "darwin":
        print("[Pulse] WARNING: audio alert skipped — afplay is macOS-only")
        return
    for _ in range(times):
        subprocess.run(["afplay", ALERT_SOUND])
        time.sleep(0.6)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip",       default=ORACLE_IP, help="Oracle server IP")
    parser.add_argument("--interval", type=int, default=10, help="Check interval in minutes")
    args = parser.parse_args()

    interval_s = args.interval * 60
    print(f"[Pulse] Monitoring {args.ip} every {args.interval} min  — Ctrl+C to stop\n")

    consecutive_failures = 0

    while True:
        now   = datetime.datetime.now().strftime("%H:%M:%S")
        alive = ping(args.ip)

        if alive:
            consecutive_failures = 0
            print(f"[{now}]  ✅  {args.ip} — alive")
        else:
            consecutive_failures += 1
            print(f"[{now}]  ❌  {args.ip} — NO RESPONSE  (failure #{consecutive_failures})")
            beep(3)

        time.sleep(interval_s)


if __name__ == "__main__":
    main()

"""
Reads /tmp/tick_logs.txt and /tmp/oracle_params.txt,
counts signal blockers, and prints the optimization decision.

Actual log patterns from agents.py:
  [TICK]      — every candle processed
  [CONSENSUS] No signal from Technical: Low volume ... — skipping
  [CONSENSUS] No signal from Technical: 4h trend opposes 1h ... — skipping
  [CONSENSUS] No signal from Technical: Trend — conditions not met (RSI=...)
  [CONSENSUS] Blocked by Risk: ...
"""
import re

with open("/tmp/tick_logs.txt") as f:
    logs = f.read()
with open("/tmp/oracle_params.txt") as f:
    params = f.read()

ticks     = len(re.findall(r'\[TICK\]', logs))
vol_blocks = len(re.findall(r'Low volume.*skipping', logs))
rsi_blocks = len(re.findall(r'conditions not met.*RSI|No mean-reversion trigger', logs))
mtf_blocks = len(re.findall(r'4h trend opposes', logs))
risk_blocks = len(re.findall(r'\[CONSENSUS\] Blocked by Risk', logs))
total_holds = vol_blocks + rsi_blocks + mtf_blocks + risk_blocks

vol_min = re.search(r'VOLUME_SPIKE_MIN=([\d.]+)', params)
current_vol = float(vol_min.group(1)) if vol_min else 1.5

print(f"TICKS={ticks}")
print(f"VOL_BLOCKS={vol_blocks}")
print(f"RSI_BLOCKS={rsi_blocks}")
print(f"MTF_BLOCKS={mtf_blocks}")
print(f"RISK_BLOCKS={risk_blocks}")
print(f"TOTAL_HOLDS={total_holds}")
print(f"CURRENT_VOL={current_vol}")

if ticks < 50:
    print("DECISION=none")
    print(f"REASON=Only {ticks} ticks in logs — need 50+ to analyse")
elif total_holds == 0:
    print("DECISION=none")
    print("REASON=No blocks found — bot is passing all filters, parameters look good")
elif vol_blocks / max(total_holds, 1) > 0.5:
    proposed = max(0.8, round(current_vol - 0.2, 1))
    print("DECISION=VOLUME_SPIKE_MIN")
    print(f"PROPOSED={proposed}")
    print(f"REASON=Volume filter blocked {vol_blocks}/{total_holds} entries ({vol_blocks * 100 // total_holds}%)")
elif mtf_blocks / max(total_holds, 1) > 0.4:
    print("DECISION=none")
    print("REASON=4h MTF is bearish — market condition, not a parameter problem")
else:
    print("DECISION=none")
    print("REASON=No clear parameter problem found")

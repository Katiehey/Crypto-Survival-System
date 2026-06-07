"""
Reads /tmp/tick_logs.txt and /tmp/oracle_params.txt,
counts signal blockers, and prints the optimization decision.
"""
import re

with open("/tmp/tick_logs.txt") as f:
    logs = f.read()
with open("/tmp/oracle_params.txt") as f:
    params = f.read()

vol_blocks = len(re.findall(r'Low volume', logs))
rsi_blocks = len(re.findall(r'RSI.*skipping|skipping.*RSI', logs, re.IGNORECASE))
mtf_blocks = len(re.findall(r'4h|bearish.*blocked|MTF', logs, re.IGNORECASE))
total_blocks = vol_blocks + rsi_blocks + mtf_blocks
ticks = len(re.findall(r'\[TICK\]', logs))

vol_min = re.search(r'VOLUME_SPIKE_MIN=([\d.]+)', params)
current_vol = float(vol_min.group(1)) if vol_min else 1.5

print(f"TICKS={ticks}")
print(f"VOL_BLOCKS={vol_blocks}")
print(f"RSI_BLOCKS={rsi_blocks}")
print(f"MTF_BLOCKS={mtf_blocks}")
print(f"TOTAL_BLOCKS={total_blocks}")
print(f"CURRENT_VOL={current_vol}")

if total_blocks == 0:
    print("DECISION=none")
    print("REASON=No blocks found — not enough data")
elif vol_blocks / max(total_blocks, 1) > 0.6:
    proposed = max(0.8, round(current_vol - 0.2, 1))
    print("DECISION=VOLUME_SPIKE_MIN")
    print(f"PROPOSED={proposed}")
    print(f"REASON=Volume filter blocked {vol_blocks}/{total_blocks} entries ({vol_blocks * 100 // total_blocks}%)")
elif mtf_blocks / max(total_blocks, 1) > 0.4:
    print("DECISION=none")
    print("REASON=4h MTF is bearish — market condition, not a parameter problem")
else:
    print("DECISION=none")
    print("REASON=No clear parameter problem found")

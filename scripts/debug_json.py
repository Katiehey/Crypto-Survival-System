import json
import glob
import os

# Find the latest metrics file
all_metrics = glob.glob("backtest_results/**/metrics.json", recursive=True)
if all_metrics:
    latest = max(all_metrics, key=os.path.getmtime)
    with open(latest, 'r') as f:
        data = json.load(f)
    
    print(f"🔍 Checking file: {latest}")
    print("--------------------------------")
    # This prints all the keys available in your JSON
    for key, value in data.items():
        print(f"Key: {key:<20} | Value: {value}")
else:
    print("❌ No metrics.json found anywhere!")
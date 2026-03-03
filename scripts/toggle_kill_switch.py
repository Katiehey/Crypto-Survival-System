#!/usr/bin/env python3
"""Toggle the repository-level kill switch under `ops/kill_switch.json`.

Usage:
  python scripts/toggle_kill_switch.py on --reason "Maintenance" --user alice
  python scripts/toggle_kill_switch.py off --user alice
"""
import json
import sys
import pathlib
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
KS = ROOT / 'ops' / 'kill_switch.json'

def load():
    try:
        return json.loads(KS.read_text())
    except Exception:
        return {"active": False, "reason": "", "updated_by": "", "timestamp": ""}

def save(obj):
    KS.write_text(json.dumps(obj, indent=2))

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('on', 'off'):
        print('Usage: toggle_kill_switch.py on|off [--reason "..."] [--user name]')
        sys.exit(2)

    action = sys.argv[1]
    reason = ''
    user = 'unknown'
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a == '--reason' and i+1 < len(args):
            reason = args[i+1]
        if a == '--user' and i+1 < len(args):
            user = args[i+1]

    obj = load()
    obj['active'] = (action == 'on')
    obj['reason'] = reason
    obj['updated_by'] = user
    obj['timestamp'] = datetime.utcnow().isoformat() + 'Z'
    save(obj)
    print(f"Kill switch set to {obj['active']} by {user}")

if __name__ == '__main__':
    main()

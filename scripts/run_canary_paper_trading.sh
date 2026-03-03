#!/usr/bin/env bash
# Run a monitored paper trading canary with the promoted baseline.
# Edit `CANARY_DURATION_HOURS` to change run length.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.
# Enable canary mode flag the system uses
export CANARY_ENABLED=true
# Point to the canary model dir (promoted baseline)
export CANARY_MODEL_DIR="models/production/production_retrained_winsor_quantile_long"
# Duration and logging
CANARY_DURATION_HOURS=${1:-24}
LOG_DIR="logs/canary_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"
# Run paper trading in dry-run/paper mode and stream logs to file
python scripts/run_paper_trading_live.py --model-dir "$CANARY_MODEL_DIR" --duration-hours "$CANARY_DURATION_HOURS" 2>&1 | tee "$LOG_DIR/canary.log"

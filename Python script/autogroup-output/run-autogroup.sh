#!/usr/bin/env bash
# Run autogroup via run-phx.py and capture the full terminal session (stdout+stderr)
# to autogroup-output/run-logs/, matching batch-upload's upload-logs/ tee pattern.
#
# The orchestrator also writes autogroup-output/<timestamp>/terminal.log for
# autogroup-phase output only; this script captures the entire run-phx.py session
# (banners, execution report, errors.log summary, etc.).
#
# Usage (from repo root):
#   set -a && source ./local.env && set +a
#   ./autogroup-output/run-autogroup.sh "$CLIENT_ID" "$CLIENT_SECRET" \
#     --api_domain "$api_domain_demo2" \
#     --action_autogroup=true
#
# Log file: autogroup-output/run-logs/autogroup_YYYYMMDD_HHMMSS.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

RUN_LOGS_DIR="$REPO_ROOT/autogroup-output/run-logs"
mkdir -p "$RUN_LOGS_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$RUN_LOGS_DIR/autogroup_${TS}.log"

if [[ -f "$REPO_ROOT/local.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_ROOT/local.env"
  set +a
fi

PYTHON="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON=python3
fi

echo "Writing full run-phx session log to: $LOG_FILE"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')" | tee "$LOG_FILE"
echo "Command: $PYTHON run-phx.py $*" | tee -a "$LOG_FILE"
echo "---" | tee -a "$LOG_FILE"

"$PYTHON" run-phx.py "$@" 2>&1 | tee -a "$LOG_FILE"
exit "${PIPESTATUS[0]}"

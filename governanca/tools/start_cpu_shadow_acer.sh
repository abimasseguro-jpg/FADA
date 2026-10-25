#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="$ROOT/governanca/evidencias/cpu_live_shadow"
PID_FILE="$STATE_DIR/service.pid"
LOG_FILE="$STATE_DIR/service.log"
mkdir -p "$STATE_DIR"

if [[ -f "$PID_FILE" ]]; then
  pid="$(tr -cd '0-9' < "$PID_FILE")"
  if [[ -n "$pid" ]] && ps -p "$pid" -o args= 2>/dev/null |
      grep -Fq "run_cpu_live_shadow_service.py --root $ROOT"; then
    echo "[FADA_CPU_SHADOW] already_running pid=$pid"
    exit 0
  fi
fi

ssh -o BatchMode=yes -o ConnectTimeout=6 codex-acer \
  "cd /home/abimas/ARTIGOS/FADA-cpu-shadow && bash governanca/tools/start_sentinela.sh"
setsid python3 "$ROOT/experiments/run_cpu_live_shadow_service.py" \
  --root "$ROOT" "$@" >>"$LOG_FILE" 2>&1 &
pid="$!"
echo "$pid" > "$PID_FILE"
echo "[FADA_CPU_SHADOW] started pid=$pid log=$LOG_FILE"

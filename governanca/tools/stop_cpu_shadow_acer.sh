#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="$ROOT/governanca/evidencias/cpu_live_shadow/service.pid"
pid=""
if [[ -r "$PID_FILE" ]]; then
  pid="$(tr -cd '0-9' < "$PID_FILE")"
fi
if [[ -n "$pid" ]] && ps -p "$pid" -o args= 2>/dev/null |
    grep -Fq "run_cpu_live_shadow_service.py --root $ROOT"; then
  kill -TERM "$pid"
  for _ in $(seq 1 20); do
    ps -p "$pid" >/dev/null 2>&1 || break
    sleep 0.5
  done
  echo "[FADA_CPU_SHADOW] stopped pid=$pid"
else
  echo "[FADA_CPU_SHADOW] already_stopped"
fi
rm -f "$PID_FILE"
ssh -o BatchMode=yes -o ConnectTimeout=6 codex-acer \
  "cd /home/abimas/ARTIGOS/FADA-cpu-shadow && bash governanca/tools/stop_sentinela.sh"

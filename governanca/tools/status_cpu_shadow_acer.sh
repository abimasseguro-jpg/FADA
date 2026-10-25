#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="$ROOT/governanca/evidencias/cpu_live_shadow"
PID_FILE="$STATE_DIR/service.pid"
STATE_FILE="$STATE_DIR/state.json"
pid=""
if [[ -r "$PID_FILE" ]]; then
  pid="$(tr -cd '0-9' < "$PID_FILE")"
fi

if [[ -n "$pid" ]] && ps -p "$pid" -o args= 2>/dev/null |
    grep -Fq "run_cpu_live_shadow_service.py --root $ROOT"; then
  process_status="running"
else
  process_status="stopped"
fi
if [[ -r "$STATE_FILE" ]]; then
  state="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("status=%s samples=%s errors=%s" % (d.get("status"), d.get("samples_completed"), d.get("errors")))' "$STATE_FILE")"
else
  state="status=uninitialized samples=0 errors=0"
fi
echo "[FADA_CPU_SHADOW] process=$process_status $state"
ssh -o BatchMode=yes -o ConnectTimeout=6 codex-acer \
  "cd /home/abimas/ARTIGOS/FADA-cpu-shadow && bash governanca/tools/status_sentinela.sh"

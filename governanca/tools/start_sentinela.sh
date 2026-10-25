#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="$ROOT/governanca/evidencias/.sentinela.pid"
OUT_FILE="$ROOT/governanca/evidencias/sentinela_watch.out"
mkdir -p "$(dirname "$PID_FILE")"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(tr -cd '0-9' < "$PID_FILE")"
  if [[ -n "$old_pid" ]] && ps -p "$old_pid" -o args= 2>/dev/null |
      grep -F "sentinela_watch.py" | grep -Fq -- "--root $ROOT"; then
    echo "[sentinela] já ativo: pid=$old_pid"
    exit 0
  fi
fi

setsid python3 "$ROOT/governanca/tools/sentinela_watch.py" \
  --root "$ROOT" --interval 2 >"$OUT_FILE" 2>&1 &
pid="$!"
echo "$pid" > "$PID_FILE"
echo "[sentinela] iniciado: pid=$pid"
python3 "$ROOT/governanca/tools/sentinela_ai.py" status --root "$ROOT"

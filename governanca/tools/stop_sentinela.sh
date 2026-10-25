#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="$ROOT/governanca/evidencias/.sentinela.pid"
pid=""
if [[ -r "$PID_FILE" ]]; then
  pid="$(tr -cd '0-9' < "$PID_FILE")"
fi
if [[ -n "$pid" ]] && ps -p "$pid" -o args= 2>/dev/null |
    grep -F "sentinela_watch.py" | grep -Fq -- "--root $ROOT"; then
  kill "$pid"
  echo "[sentinela] parado: pid=$pid"
else
  echo "[sentinela] inativo"
fi
rm -f "$PID_FILE"

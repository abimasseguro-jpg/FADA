#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 "$project_root/governanca/tools/sentinela_ai.py" status --root "$project_root"
python3 "$project_root/governanca/tools/sentinela_fada.py" status --root "$project_root"
python3 "$project_root/governanca/tools/sentinela_memory.py" status --root "$project_root"

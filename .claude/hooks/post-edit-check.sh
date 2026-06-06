#!/usr/bin/env bash
# Runs after Edit/Write. Fast sanity check on the edited file — never blocks.
# Reads the hook payload from stdin, extracts the path, lints Python files.

set -euo pipefail

payload="$(cat)"
path="$(printf '%s' "$payload" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("tool_input",{}).get("file_path",""))' 2>/dev/null || true)"

[ -z "$path" ] && exit 0
[ ! -f "$path" ] && exit 0

case "$path" in
  *.py)
    uv run ruff check --quiet "$path" 2>&1 | head -20 || true
    ;;
esac

exit 0

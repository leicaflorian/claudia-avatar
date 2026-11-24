#!/usr/bin/env bash
# Called by the plugin's hooks: updates the state the status line draws.
# It never blocks or approves anything, and prints nothing.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${CLAUDIA_HOME:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/claudia-avatar}"
mkdir -p "$HOME_DIR/state"
input=$(cat)

# On session start, refresh the stable copy of the status line and its art.
case "$input" in *'"SessionStart"'*) "$ROOT/scripts/sync.sh";; esac

if command -v node >/dev/null 2>&1; then printf '%s' "$input" | node "$ROOT/scripts/hook.mjs" "$HOME_DIR"
elif command -v python3 >/dev/null 2>&1; then printf '%s' "$input" | python3 "$ROOT/scripts/hook.py" "$HOME_DIR"
else
  # Last resort: basic state only, no extras.
  sid=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | tr -cd 'a-zA-Z0-9_-')
  printf 'talk %s\nworking…\n\n' "$(date +%s)" > "$HOME_DIR/state/${sid:-default}"
fi
exit 0

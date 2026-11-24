#!/usr/bin/env bash
# Copies the status line and its art to a stable folder (~/.claude/claudia-avatar/app):
# the plugin folder changes with every update, the status line path must not.
# Usage: sync.sh [--force]
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${CLAUDIA_HOME:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/claudia-avatar}"
mkdir -p "$HOME_DIR/state"
[ "${1:-}" != --force ] && [ "$(cat "$HOME_DIR/app/.source" 2>/dev/null)" = "$ROOT" ] && exit 0
tmp="$HOME_DIR/app.tmp.$$"; rm -rf "$tmp"; mkdir -p "$tmp"
if cp -R "$ROOT/art" "$ROOT/scripts/statusline.sh" "$ROOT/scripts/banner.sh" "$tmp/" 2>/dev/null; then
  printf '%s\n' "$ROOT" > "$tmp/.source"; chmod +x "$tmp"/*.sh
  rm -rf "$HOME_DIR/app.old"; [ -d "$HOME_DIR/app" ] && mv "$HOME_DIR/app" "$HOME_DIR/app.old"
  mv "$tmp" "$HOME_DIR/app" && rm -rf "$HOME_DIR/app.old"
else rm -rf "$tmp"; exit 1; fi

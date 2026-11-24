#!/usr/bin/env bash
# Animated startup banner: a blink and a smile (about 1.5 s).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$DIR/art" ]; then ART="$DIR/art"; HOME_DIR="$(dirname "$DIR")"
else ART="$DIR/../art"; HOME_DIR="${CLAUDIA_HOME:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/claudia-avatar}"; fi
# Colors: truecolor if the terminal declares it, otherwise the 256-color palette
# (e.g. the JetBrains terminal). Force with CLAUDIA_COLORS=truecolor|256.
case "${CLAUDIA_COLORS:-${COLORTERM:-}}" in truecolor|24bit) SFX="";; *) SFX="256";; esac
# Style: the one chosen with the setup command (see statusline.sh). Force with CLAUDIA_STYLE.
style=portrait
if [ -f "$HOME_DIR/style" ]; then read -r v < "$HOME_DIR/style"; [[ $v =~ ^[a-z0-9_-]+$ ]] && style=$v; fi
STYLE="${CLAUDIA_STYLE:-$style}"; [ -d "$ART/$STYLE/banner" ] || STYLE=portrait
FRAMES="$ART/$STYLE/banner$SFX"
seq=(idle idle blink idle talk1 idle happy happy)   # frames built by build-art.py (BANNER)
H=$(wc -l < "$FRAMES/idle.ans")
printf '\e[?25l'
for k in "${!seq[@]}"; do
  (( k > 0 )) && printf '\e[%dA' "$H"
  cat "$FRAMES/${seq[$k]}.ans"; sleep 0.18
done
printf '\e[?25h  \e[38;2;242;112;38mClaudia\e[0m \e[2m· open character by anabology (claudia.gallery)\e[0m\n\n'

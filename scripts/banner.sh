#!/usr/bin/env bash
# Animated startup banner: a blink and a smile (about 1.5 s).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ART="$DIR/art"; [ -d "$ART" ] || ART="$DIR/../art"
# Colors: truecolor if the terminal declares it, otherwise the 256-color palette
# (e.g. the JetBrains terminal). Force with CLAUDIA_COLORS=truecolor|256.
case "${CLAUDIA_COLORS:-${COLORTERM:-}}" in truecolor|24bit) SFX="";; *) SFX="256";; esac
seq=(idle idle blink idle talk1 idle happy happy)
H=$(wc -l < "$ART/banner$SFX/idle.ans")
printf '\e[?25l'
for k in "${!seq[@]}"; do
  (( k > 0 )) && printf '\e[%dA' "$H"
  cat "$ART/banner$SFX/${seq[$k]}.ans"; sleep 0.18
done
printf '\e[?25h  \e[38;2;242;112;38mClaudia\e[0m \e[2m· open character by anabology (claudia.gallery)\e[0m\n\n'

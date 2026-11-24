#!/usr/bin/env bash
# Claudia status line: expression and animation based on what Claude is doing,
# plus context, cost and the last test result. Runs from the copy in
# ~/.claude/claudia-avatar/app (or straight from scripts/ during development).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$DIR/art" ]; then ART="$DIR/art"; HOME_DIR="$(dirname "$DIR")"
else ART="$DIR/../art"; HOME_DIR="${CLAUDIA_HOME:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/claudia-avatar}"; fi
mkdir -p "$HOME_DIR/state"

# config (written by the hooks at every session start, from the plugin options)
size=small ctx_warn=60 ctx_alarm=85 cost_warn=2 cost_alarm=5
if [ -f "$HOME_DIR/config" ]; then
  while IFS='=' read -r k v; do case "$k" in
    size) [[ $v =~ ^(small|large)$ ]] && size=$v;;
    ctx_warn|ctx_alarm|cost_warn|cost_alarm) [[ $v =~ ^[0-9]+(\.[0-9]+)?$ ]] && printf -v "$k" '%s' "$v";;
  esac; done < "$HOME_DIR/config"
fi
[ "${CLAUDIA_SIZE:-$size}" = large ] && SZ="" || SZ="S"
case "${CLAUDIA_COLORS:-${COLORTERM:-}}" in truecolor|24bit) SFX="";; *) SFX="256";; esac

input=$(cat)
get() { printf '%s' "$input" | tr -d '\n' | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -1; }
num() { printf '%s' "$input" | tr -d '\n' | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\([0-9][0-9.eE+-]*\).*/\1/p" | head -1; }
sid=$(get session_id | tr -cd 'a-zA-Z0-9_-'); model=$(get display_name); cwd=$(get current_dir); [ -z "$cwd" ] && cwd="$PWD"
pct=$(num used_percentage); cost=$(num total_cost_usd)

sf="$HOME_DIR/state/${sid:-default}"
{ read -r state ts; read -r label; IFS=$'\t' read -r tres ttext; } 2>/dev/null < "$sf" || { state=idle; ts=$(date +%s); label="ready"; }
age=$(( $(date +%s) - ${ts:-0} ))
n=$(( $(cat "$sf.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$sf.n"; ab=$(( n % 2 + 1 ))

case "$state" in
  think|read|type|talk|web|wait|compact) f="$state$ab";;
  error) if (( age < 60 )); then f="error$ab"; else f=idle; label="ready"; fi;;
  wink)  f=wink;;
  happy) if (( age < 20 )); then f=happy; else f="talk$ab"; label="working…"; fi;;
  done)  if (( age < 45 )); then f=happy; else f=idle; fi;;
  *)     f=idle;;
esac

# levels: 0 ok, 1 warning, 2 alarm
lvl() { LC_ALL=C awk -v x="${1:-0}" -v w="$2" -v a="$3" 'BEGIN{print (x>=a)?2:(x>=w)?1:0}'; }
cl=$(lvl "$pct" "$ctx_warn" "$ctx_alarm"); kl=$(lvl "$cost" "$cost_warn" "$cost_alarm")

# When Claudia is idle and context or cost is in alarm, she says so.
if [[ $f == idle ]]; then
  if (( cl == 2 )); then f="wait$ab"; label="context at ${pct%.*}%: time to /compact?"
  elif (( kl == 2 )); then f="wait$ab"; label="session over \$$cost_alarm"
  elif (( age > 600 )); then f=sleep; label="zzz"
  elif (( RANDOM % 5 == 0 )); then f=blink; fi
fi
[ -f "$ART/frames$SZ$SFX/$f.ans" ] || f=idle

# colors
R=$'\e[0m'; D=$'\e[2m'
if [ "$SFX" = 256 ]; then O=$'\e[38;5;208m'; C=($'\e[38;5;108m' $'\e[38;5;179m' $'\e[38;5;167m')
else O=$'\e[38;2;242;112;38m'; C=($'\e[38;2;143;185;138m' $'\e[38;2;224;180;90m' $'\e[38;2;224;108;90m'); fi

branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
meter=""
if [ -n "$pct" ]; then
  p=${pct%.*}; k=$(( (p + 5) / 10 )); (( k > 10 )) && k=10
  bar=$(printf '%*s' "$k" '' | sed 's/ /█/g'); rest=$(printf '%*s' $((10 - k)) '' | sed 's/ /░/g')
  meter="${C[$cl]}${bar}${R}${D}${rest} ${p}% ctx${R}"
fi
if [ -n "$cost" ]; then
  c=$(LC_ALL=C awk -v x="$cost" 'BEGIN{printf "%.2f", x}')
  meter="${meter:+$meter ${D}·${R} }${C[$kl]}\$$c${R}"
fi
tests=""
case "$tres" in ok) tests="${C[0]}${ttext}${R}";; fail) tests="${C[2]}${ttext}${R}";; esac

l1="${O}●${R} ${model:-Claude} ${D}·${R} ${label}"
l2="${D}${cwd##*/}${branch:+  ⎇ $branch}${R}"
if [ -n "$SZ" ]; then info=( "" "$l1" "$l2" "$meter" "$tests" "" "" )
else info=( "" "" "$l1" "$l2" "$meter" "$tests" "" "" "" "" ); fi
i=0
while IFS= read -r line; do printf '%s  %s\n' "$line" "${info[$i]}"; i=$((i+1)); done < "$ART/frames$SZ$SFX/$f.ans"

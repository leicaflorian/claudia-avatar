#!/usr/bin/env bash
# Sets up Claudia's status line in ~/.claude/settings.json (a plugin cannot do this by itself).
# Usage: setup.sh install [--force] [--banner|--no-banner] [--style=NAME]
#        setup.sh style NAME      pick the avatar style (a folder in art/), effective at once
#        setup.sh uninstall
#        setup.sh status
# Exit codes: 0 ok · 3 another status line is already set (re-run with --force) · 1 error
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HOME_DIR="${CLAUDIA_HOME:-$CFG/claudia-avatar}"
SETTINGS="$CFG/settings.json"
CMD="$HOME_DIR/app/statusline.sh"
MARK_START="# >>> claudia-avatar >>>"; MARK_END="# <<< claudia-avatar <<<"

MODE="${1:-install}"; shift || true
FORCE=0; BANNER=keep; STYLE=""
if [ "$MODE" = style ]; then STYLE="${1:-}"; shift || true; fi
for a in "$@"; do case "$a" in
  --force) FORCE=1;; --banner) BANNER=on;; --no-banner) BANNER=off;;
  --style=*) STYLE="${a#--style=}";;
  *) echo "unknown option: $a" >&2; exit 1;;
esac; done

# --- style: kept in its own file, which the status line and the banner read ---------
styles() { for d in "$ROOT"/art/*/frames; do if [ -d "$d" ]; then basename "$(dirname "$d")"; fi; done | paste -sd ' ' -; }
current_style() { local s=""; if [ -f "$HOME_DIR/style" ]; then read -r s < "$HOME_DIR/style" || true; fi; echo "${s:-portrait}"; }
check_style() { # $1 = name
  if [[ ! $1 =~ ^[a-z0-9_-]+$ ]] || [ ! -d "$ROOT/art/$1/frames" ]; then
    echo "unknown style: ${1:-(none given)} (available: $(styles))" >&2; exit 1
  fi
}
set_style() { mkdir -p "$HOME_DIR"; printf '%s\n' "$1" > "$HOME_DIR/style"; echo "style: $1"; }
if [ -n "$STYLE" ] || [ "$MODE" = style ]; then check_style "$STYLE"; fi

# --- settings.json: status line, and cleanup of older manual installs -------------
# Removes the hooks that earlier installers (install.sh and claudia-companion) put in
# settings.json: the hooks now come from the plugin.
JS='
const fs=require("fs"),[file,cmd,mode,force]=process.argv.slice(1);
let s={};
if(fs.existsSync(file)){const t=fs.readFileSync(file,"utf8").trim();try{s=JSON.parse(t||"{}")}catch(e){console.error("settings.json is not valid JSON: leaving it alone");process.exit(1)}}
const legacy=c=>/claudia-avatar\/state\.sh|claudia\.mjs/.test(String(c||""));
const ours=c=>/claudia-avatar\/(app\/)?statusline\.sh|claudia\.mjs/.test(String(c||""));
const cur=s.statusLine&&s.statusLine.command;
if(mode==="status"){console.log(JSON.stringify({statusLine:s.statusLine||null,ours:ours(cur),legacyHooks:Object.values(s.hooks||{}).flat().some(g=>(g.hooks||[]).some(h=>legacy(h.command)))}));process.exit(0)}
if(mode==="install"&&cur&&!ours(cur)&&force!=="1"){console.log(JSON.stringify(s.statusLine));process.exit(3)}
let removed=0;
if(s.hooks){for(const k of Object.keys(s.hooks)){
  s.hooks[k]=(s.hooks[k]||[]).map(g=>{const hs=(g.hooks||[]).filter(h=>!legacy(h.command));removed+=(g.hooks||[]).length-hs.length;return{...g,hooks:hs}}).filter(g=>g.hooks.length);
  if(!s.hooks[k].length)delete s.hooks[k]}
  if(!Object.keys(s.hooks).length)delete s.hooks}
if(mode==="install")s.statusLine={type:"command",command:/\s/.test(cmd)?JSON.stringify(cmd):cmd,padding:0,refreshInterval:2};
else if(ours(cur))delete s.statusLine;
fs.writeFileSync(file,JSON.stringify(s,null,2)+"\n");
if(removed)console.log("removed-legacy-hooks="+removed);'
PY='
import json,os,re,sys
file,cmd,mode,force=sys.argv[1:5]
s={}
if os.path.exists(file):
    t=open(file).read().strip()
    try: s=json.loads(t or "{}")
    except Exception: sys.exit("settings.json is not valid JSON: leaving it alone")
legacy=lambda c: bool(re.search(r"claudia-avatar/state\.sh|claudia\.mjs",str(c or "")))
ours=lambda c: bool(re.search(r"claudia-avatar/(app/)?statusline\.sh|claudia\.mjs",str(c or "")))
cur=(s.get("statusLine") or {}).get("command")
if mode=="status":
    print(json.dumps({"statusLine":s.get("statusLine"),"ours":ours(cur),"legacyHooks":any(legacy(h.get("command")) for gs in (s.get("hooks") or {}).values() for g in gs for h in g.get("hooks",[]))})); sys.exit(0)
if mode=="install" and cur and not ours(cur) and force!="1":
    print(json.dumps(s["statusLine"])); sys.exit(3)
removed=0
h=s.get("hooks") or {}
for k in list(h):
    gs=[]
    for g in h[k]:
        hs=[x for x in g.get("hooks",[]) if not legacy(x.get("command"))]; removed+=len(g.get("hooks",[]))-len(hs)
        if hs: gs.append(dict(g,hooks=hs))
    if gs: h[k]=gs
    else: del h[k]
if "hooks" in s:
    if h: s["hooks"]=h
    else: del s["hooks"]
if mode=="install": s["statusLine"]={"type":"command","command":json.dumps(cmd) if re.search(r"\s",cmd) else cmd,"padding":0,"refreshInterval":2}
elif ours(cur): del s["statusLine"]
open(file,"w").write(json.dumps(s,indent=2)+"\n")
if removed: print(f"removed-legacy-hooks={removed}")'
settings() { # $1 = install|uninstall|status
  mkdir -p "$CFG"
  if [ "$1" != status ] && [ -f "$SETTINGS" ]; then cp "$SETTINGS" "$SETTINGS.bak-claudia-$(date +%Y%m%d%H%M%S)"; fi
  set +e
  if command -v node >/dev/null; then node -e "$JS" "$SETTINGS" "$CMD" "$1" "$FORCE"
  elif command -v python3 >/dev/null; then python3 -c "$PY" "$SETTINGS" "$CMD" "$1" "$FORCE"
  else echo "node or python3 is needed to edit settings.json" >&2; return 1; fi
  local rc=$?; set -e; return $rc
}

rc_files() { for f in "$HOME/.bashrc" "$HOME/.zshrc"; do [ -f "$f" ] && echo "$f"; done; return 0; }
remove_banner() {
  for f in $(rc_files); do
    if grep -qF "$MARK_START" "$f"; then
      awk -v s="$MARK_START" -v e="$MARK_END" '$0==s{skip=1;next} $0==e{skip=0;next} !skip' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
      echo "startup banner removed from $f"
    fi
  done
}
add_banner() {
  remove_banner >/dev/null
  local rcs; rcs=$(rc_files); [ -z "$rcs" ] && { touch "$HOME/.bashrc"; rcs="$HOME/.bashrc"; }
  for f in $rcs; do
    if [ -s "$f" ] && [ -n "$(tail -c1 "$f")" ]; then echo >> "$f"; fi
    printf '%s\nclaude() { [ -x "%s/app/banner.sh" ] && "%s/app/banner.sh"; command claude "$@"; }\n%s\n' \
      "$MARK_START" "$HOME_DIR" "$HOME_DIR" "$MARK_END" >> "$f"
    echo "startup banner added to $f"
  done
}
# Files left by the old install.sh in the same folder
clean_legacy_files() {
  local n=0
  for x in "$HOME_DIR"/frames* "$HOME_DIR"/banner "$HOME_DIR"/banner256 "$HOME_DIR"/.state \
           "$HOME_DIR"/statusline.sh "$HOME_DIR"/state.sh "$HOME_DIR"/banner.sh "$HOME_DIR"/install.sh "$HOME_DIR"/README.md; do
    [ -e "$x" ] && { rm -rf "$x"; n=$((n+1)); }
  done
  [ $n -gt 0 ] && echo "removed $n files of the old manual install from $HOME_DIR"
  return 0
}

case "$MODE" in
  status)
    settings status
    echo "app: $( [ -x "$CMD" ] && echo "present ($(cat "$HOME_DIR/app/.source" 2>/dev/null))" || echo missing)"
    if grep -qsF "$MARK_START" "$HOME/.bashrc" "$HOME/.zshrc"; then echo "banner: on"; else echo "banner: off"; fi
    echo "style: $(current_style) (available: $(styles))"
    [ -d "$CFG/claudia" ] && echo "note: the claudia-companion folder is still in $CFG/claudia"
    exit 0;;
  style)
    set_style "$STYLE"
    exit 0;;
  install)
    "$ROOT/scripts/sync.sh" --force
    clean_legacy_files
    set +e; out=$(settings install); rc=$?; set -e
    if [ $rc -eq 3 ]; then echo "OTHER_STATUSLINE $out"; exit 3; fi
    [ $rc -ne 0 ] && { echo "$out"; exit 1; }
    [ -n "$out" ] && echo "removed ${out#removed-legacy-hooks=} hooks of the old install from settings.json"
    echo "status line set: $CMD (settings.json backup saved next to it)"
    case "$BANNER" in on) add_banner;; off) remove_banner;; esac
    if [ -n "$STYLE" ]; then set_style "$STYLE"; else echo "style: $(current_style)"; fi
    [ -d "$CFG/claudia" ] && echo "note: the claudia-companion folder ($CFG/claudia) is no longer needed and can be deleted"
    exit 0;;
  uninstall)
    settings uninstall >/dev/null && echo "status line and old hooks removed from settings.json (backup saved next to it)"
    remove_banner
    rm -rf "$HOME_DIR" && echo "removed $HOME_DIR"
    exit 0;;
  *) echo "usage: setup.sh install|uninstall|status|style NAME" >&2; exit 1;;
esac

# Claudia: hook logic (Python), used when Node is not available.
# Same behaviour as hook.mjs: keep them in sync.
# Usage: python3 hook.py <state-dir>
import json, os, re, subprocess, sys, time

HOME = sys.argv[1]
STATE = os.path.join(HOME, "state")
now = int(time.time() * 1000)

DEFAULTS = {"size": "small", "notify": "on", "notify_after": 30, "ctx_warn": 60, "ctx_alarm": 85, "cost_warn": 2, "cost_alarm": 5}
cfg = {}
for k, d in DEFAULTS.items():
    v = os.environ.get("CLAUDE_PLUGIN_OPTION_" + k.upper(), os.environ.get("CLAUDE_PLUGIN_OPTION_" + k, str(d))).strip()
    if isinstance(d, (int, float)):
        try:
            f = float(v); cfg[k] = int(f) if f.is_integer() else f
        except ValueError:
            cfg[k] = d
    else:
        cfg[k] = v if re.fullmatch(r"[a-z]+", v) else d

raw = sys.stdin.read()
try:
    j = json.loads(raw)
except Exception:
    m = re.search(r'"session_id"\s*:\s*"([^"]*)"', raw)
    j = {"session_id": m.group(1) if m else None}
ev = j.get("hook_event_name") or ""
t = j.get("tool_name") or ""
i = j.get("tool_input") or {}
sid = re.sub(r"[^a-zA-Z0-9_-]", "", str(j.get("session_id") or "default"))[:80] or "default"
json_file = os.path.join(STATE, sid + ".json")
txt_file = os.path.join(STATE, sid)
os.makedirs(STATE, exist_ok=True)

if ev == "SessionEnd":
    for f in (json_file, txt_file, txt_file + ".n"):
        try: os.unlink(f)
        except OSError: pass
    sys.exit(0)

try:
    s = json.load(open(json_file))
except Exception:
    s = {}
s.setdefault("turn", {"start": now, "tools": 0, "files": [], "errors": 0})

base = lambda p: re.split(r"[\\/]", str(p or ""))[-1]
def cut(x, n=34):
    x = " ".join(str(x or "").split()); return x if len(x) <= n else x[:n - 1] + "…"
def dur(ms):
    sec = round(ms / 1000); return f"{sec}s" if sec < 60 else f"{sec // 60}m{sec % 60:02d}s"
def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"

def notify(kind, title, msg):
    if cfg["notify"] != "on": return
    s.setdefault("notified", {})
    if now - s["notified"].get(kind, 0) < 15000: return
    s["notified"][kind] = now
    def run(args):
        try: subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception: pass
    if sys.platform == "darwin":
        run(["osascript", "-e", "on run argv", "-e", 'display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"', "-e", "end run", title, msg])
    elif sys.platform.startswith("linux") and not os.environ.get("WSL_DISTRO_NAME"):
        run(["notify-send", "-a", "Claudia", title, msg])

TEST_RE = re.compile(r"(^|[\s;&|(/])(phpunit|paratest|pest|pytest|vitest|jest|rspec|phpspec|codecept(ion)?\s+run|artisan\s+test|(npm|pnpm|yarn|bun)\s+(run\s+)?test|composer\s+(run(-script)?\s+)?test|go\s+test|cargo\s+test|mvn\s+(\S+\s+)*test|gradlew?\s+(\S+\s+)*test|dotnet\s+test|mix\s+test|deno\s+test)(\s|$|:)")
is_test = lambda cmd: bool(TEST_RE.search(str(cmd or "")))

def test_result(out, failed_tool):
    out = re.sub(r"\x1b\[[0-9;]*m", "", str(out or ""))
    def num(rx):
        ms = re.findall(rx, out, re.I); return int(ms[-1]) if ms else None
    passed = num(r"(\d+)\s+(?:passed|passing)\b")
    failed = (num(r"(\d+)\s+(?:failed|failing|failures?)\b") or 0) + (num(r"(\d+)\s+errors?\b(?!:)") or 0)
    ok = re.search(r"OK \((\d+) tests?", out)
    if ok: passed = int(ok.group(1))
    pu = re.search(r"Tests:\s*(\d+),\s*Assertions:[^\n]*", out)
    if pu:
        g = lambda rx: int((re.search(rx, pu.group(0)) or [None, 0])[1] or 0)
        failed = g(r"Failures:\s*(\d+)") + g(r"Errors:\s*(\d+)"); passed = int(pu.group(1)) - failed
    fail = failed_tool or failed > 0 or (re.search(r"\bFAIL(ED|URES?)?\b", out) and not re.search(r"\b0 failed\b", out))
    total = (passed or 0) + (failed or 0)
    if not fail:
        return {"ok": True, "text": f"✓ {plural(passed, 'test passed', 'tests passed')}" if passed else "✓ tests green"}
    return {"ok": False, "text": f"✗ {failed}{'/' + str(total) if total else ''} tests failed" if failed else "✗ tests failed"}

def tool():
    if t in ("Read", "NotebookRead"): return "read", "reading " + base(i.get("file_path") or i.get("notebook_path"))
    if t in ("Grep", "Glob", "LS"): return "read", "searching " + cut(i.get("pattern") or i.get("path"), 28)
    if t in ("Edit", "MultiEdit", "Write", "NotebookEdit"): return "type", ("writing " if t == "Write" else "editing ") + base(i.get("file_path") or i.get("notebook_path"))
    if t == "TodoWrite": return "type", "updating todos"
    if t == "Bash": return ("talk", "running tests: " + cut(i.get("command"), 26)) if is_test(i.get("command")) else ("talk", "$ " + cut(i.get("command")))
    if t == "WebSearch": return "web", "searching: " + cut(i.get("query"), 28)
    if t == "WebFetch":
        m = re.match(r"https?://([^/]+)", str(i.get("url", ""))); return "web", "reading " + (m.group(1) if m else "the web")
    if t in ("Task", "Agent"): return "wink", "delegating: " + cut(i.get("description") or i.get("subagent_type"), 28)
    if t.startswith("mcp__"): return "talk", "using " + t.split("__")[1]
    return "talk", "using " + t

new_turn = lambda: {"start": now, "tools": 0, "files": [], "errors": 0}
st, lb = "talk", "working…"
if ev == "SessionStart":
    st, lb = "idle", "ready"; s["turn"] = new_turn()
    with open(os.path.join(HOME, "config"), "w") as f:
        f.write("".join(f"{k}={v}\n" for k, v in cfg.items()))
elif ev == "UserPromptSubmit":
    st, lb = "think", "thinking…"; s["turn"] = new_turn()
elif ev == "PreToolUse":
    st, lb = tool(); s["turn"]["tools"] += 1
    f = i.get("file_path") or i.get("notebook_path")
    if t in ("Edit", "MultiEdit", "Write", "NotebookEdit") and f and f not in s["turn"]["files"]: s["turn"]["files"].append(f)
elif ev == "PostToolUse":
    # A tool finished: until the next event Claude is either thinking or writing its
    # reply, and hooks can't tell which. Claudia types.
    if t != "Bash" or not is_test(i.get("command")):
        st, lb = "type", "writing…"
    else:
        r = j.get("tool_response") or {}
        out = r if isinstance(r, str) else "\n".join(x for x in (r.get("stdout"), r.get("stderr")) if x)
        s["test"] = dict(test_result(out, False), ts=now)
        st, lb = ("happy", "tests green!") if s["test"]["ok"] else ("error", "tests red")
elif ev == "PostToolUseFailure":
    if t == "Bash" and is_test(i.get("command")):
        s["test"] = dict(test_result(j.get("error"), True), ts=now); st, lb = "error", "tests red"
    else:
        st, lb = "error", t + " failed"
    s["turn"]["errors"] += 1
elif ev == "PermissionRequest":
    st, lb = "wait", "asking permission: " + t
    extra = ": " + cut(i.get("command"), 60) if t == "Bash" and i.get("command") else ""
    notify("ask", "Claudia is waiting", f"Claude needs your permission for {t}{extra}")
elif ev == "Notification":
    st, lb = "wait", "waiting for you"
    if j.get("notification_type") != "idle_prompt": notify("ask", "Claudia is waiting", j.get("message") or "Claude needs your input")
elif ev == "PreCompact": st, lb = "compact", "compacting memory…"
elif ev == "SubagentStart": st, lb = "wink", "subagent at work"
elif ev == "SubagentStop": st, lb = "talk", "subagent done"
elif ev == "Stop":
    tr = s["turn"]; ms = now - (tr.get("start") or now)
    parts = ["done in " + dur(ms)]
    if tr["files"]: parts.append(plural(len(tr["files"]), "file", "files"))
    if tr["tools"]: parts.append(plural(tr["tools"], "tool", "tools"))
    if tr["errors"]: parts.append(plural(tr["errors"], "error", "errors"))
    st, lb = "done", " · ".join(parts)
    if ms >= cfg["notify_after"] * 1000: notify("done", "Claudia is done", lb)
elif ev == "StopFailure": st, lb = "error", "stopped (API error)"
else:
    sys.exit(0)

s.update(st=st, ts=now, label=lb)
def write(f, data):
    with open(f + ".tmp", "w") as h: h.write(data)
    os.replace(f + ".tmp", f)
write(json_file, json.dumps(s))
test = f"{'ok' if s['test']['ok'] else 'fail'}\t{s['test']['text']}" if s.get("test") else ""
write(txt_file, f"{st} {now // 1000}\n{lb.replace(chr(9), ' ').replace(chr(10), ' ')}\n{test}\n")

if ev == "SessionStart":
    for f in os.listdir(STATE):
        p = os.path.join(STATE, f)
        try:
            if now / 1000 - os.stat(p).st_mtime > 2 * 86400: os.unlink(p)
        except OSError: pass

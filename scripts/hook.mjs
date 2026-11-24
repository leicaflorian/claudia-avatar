// Claudia: hook logic (Node). Reads the event from stdin, updates the session state
// and sends a desktop notification when needed. Prints nothing: the output of some
// hooks would end up in Claude's context.
// Usage: node hook.mjs <state-dir>      (hook.py does the same in Python)
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const HOME = process.argv[2];
const STATE = path.join(HOME, 'state');
const now = Date.now();

// ---------- config (plugin userConfig → a file the status line reads too)
const DEFAULTS = { size: 'small', notify: 'on', notify_after: 30, ctx_warn: 60, ctx_alarm: 85, cost_warn: 2, cost_alarm: 5 };
const opt = (k) => process.env[`CLAUDE_PLUGIN_OPTION_${k.toUpperCase()}`] ?? process.env[`CLAUDE_PLUGIN_OPTION_${k}`];
const cfg = {};
for (const [k, d] of Object.entries(DEFAULTS)) {
  const v = String(opt(k) ?? d).trim();
  cfg[k] = typeof d === 'number' ? (Number.isFinite(+v) && v !== '' ? +v : d) : (/^[a-z]+$/.test(v) ? v : d);
}

// ---------- input
let j = {};
const raw = fs.readFileSync(0, 'utf8');
try { j = JSON.parse(raw); } catch { j = { session_id: (raw.match(/"session_id"\s*:\s*"([^"]*)"/) || [])[1] }; }
const ev = j.hook_event_name || '';
const t = j.tool_name || '';
const i = j.tool_input || {};
const sid = String(j.session_id || 'default').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 80) || 'default';
const jsonFile = path.join(STATE, `${sid}.json`);
const txtFile = path.join(STATE, sid);

fs.mkdirSync(STATE, { recursive: true });

if (ev === 'SessionEnd') {
  for (const f of [jsonFile, txtFile, txtFile + '.n']) { try { fs.unlinkSync(f); } catch {} }
  process.exit(0);
}

let s = {};
try { s = JSON.parse(fs.readFileSync(jsonFile, 'utf8')); } catch {}
s.turn ||= { start: now, tools: 0, files: [], errors: 0 };

// ---------- helpers
const base = (p) => String(p || '').split(/[\\/]/).pop();
const cut = (x, n = 34) => { x = String(x || '').replace(/\s+/g, ' ').trim(); return x.length > n ? x.slice(0, n - 1) + '…' : x; };
const dur = (ms) => { const sec = Math.round(ms / 1000); return sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}m${String(sec % 60).padStart(2, '0')}s`; };
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

function notify(kind, title, msg) {
  if (cfg.notify !== 'on') return;
  s.notified ||= {};
  if (now - (s.notified[kind] || 0) < 15000) return; // no back-to-back duplicates
  s.notified[kind] = now;
  const run = (cmd, args) => { try { spawn(cmd, args, { detached: true, stdio: 'ignore' }).on('error', () => {}).unref(); } catch {} };
  if (process.platform === 'darwin') {
    run('osascript', ['-e', 'on run argv', '-e', 'display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"', '-e', 'end run', title, msg]);
  } else if (process.platform === 'linux' && !process.env.WSL_DISTRO_NAME) {
    run('notify-send', ['-a', 'Claudia', title, msg]);
  }
}

// ---------- tests: detect the command and its outcome
const TEST_RE = /(^|[\s;&|(\/])(phpunit|paratest|pest|pytest|vitest|jest|rspec|phpspec|codecept(ion)?\s+run|artisan\s+test|(npm|pnpm|yarn|bun)\s+(run\s+)?test|composer\s+(run(-script)?\s+)?test|go\s+test|cargo\s+test|mvn\s+(\S+\s+)*test|gradlew?\s+(\S+\s+)*test|dotnet\s+test|mix\s+test|deno\s+test)(\s|$|:)/;
const isTest = (cmd) => TEST_RE.test(String(cmd || ''));

function testResult(out, failedTool) {
  out = String(out || '').replace(/\x1b\[[0-9;]*m/g, '');
  const num = (re) => { let m, last = null; const g = new RegExp(re, 'gi'); while ((m = g.exec(out))) last = +m[1]; return last; };
  let passed = num('(\\d+)\\s+(?:passed|passing)\\b');
  let failed = (num('(\\d+)\\s+(?:failed|failing|failures?)\\b') || 0) + (num('(\\d+)\\s+errors?\\b(?!:)') || 0);
  // PHPUnit: "OK (12 tests, 30 assertions)" / "Tests: 12, Assertions: 30, Failures: 2, Errors: 1."
  const ok = out.match(/OK \((\d+) tests?/);
  if (ok) passed = +ok[1];
  const pu = out.match(/Tests:\s*(\d+),\s*Assertions:[^\n]*/);
  if (pu) {
    const f = (+(pu[0].match(/Failures:\s*(\d+)/) || [])[1] || 0) + (+(pu[0].match(/Errors:\s*(\d+)/) || [])[1] || 0);
    failed = f; passed = +pu[1] - f;
  }
  // cargo: "test result: FAILED. 10 passed; 2 failed;"
  const fail = failedTool || failed > 0 || /\bFAIL(ED|URES?)?\b/.test(out) && !/\b0 failed\b/.test(out);
  const total = (passed || 0) + (failed || 0);
  if (!fail) return { ok: true, text: passed ? `✓ ${plural(passed, 'test passed', 'tests passed')}` : '✓ tests green' };
  return { ok: false, text: failed ? `✗ ${failed}${total ? '/' + total : ''} tests failed` : '✗ tests failed' };
}

// ---------- event → state
let st = 'talk', lb = 'working…';
function tool() {
  if (/^(Read|NotebookRead)$/.test(t)) return ['read', 'reading ' + base(i.file_path || i.notebook_path)];
  if (/^(Grep|Glob|LS)$/.test(t)) return ['read', 'searching ' + cut(i.pattern || i.path, 28)];
  if (/^(Edit|MultiEdit|Write|NotebookEdit)$/.test(t)) return ['type', (t === 'Write' ? 'writing ' : 'editing ') + base(i.file_path || i.notebook_path)];
  if (t === 'TodoWrite') return ['type', 'updating todos'];
  if (t === 'Bash') return isTest(i.command) ? ['talk', 'running tests: ' + cut(i.command, 26)] : ['talk', '$ ' + cut(i.command)];
  if (t === 'WebSearch') return ['web', 'searching: ' + cut(i.query, 28)];
  if (t === 'WebFetch') { let h = ''; try { h = new URL(i.url).host; } catch {} return ['web', 'reading ' + (h || 'the web')]; }
  if (/^(Task|Agent)$/.test(t)) return ['wink', 'delegating: ' + cut(i.description || i.subagent_type, 28)];
  if (t.startsWith('mcp__')) return ['talk', 'using ' + t.split('__')[1]];
  return ['talk', 'using ' + t];
}

switch (ev) {
  case 'SessionStart':
    st = 'idle'; lb = 'ready';
    s.turn = { start: now, tools: 0, files: [], errors: 0 };
    fs.writeFileSync(path.join(HOME, 'config'), Object.entries(cfg).map(([k, v]) => `${k}=${v}`).join('\n') + '\n');
    break;
  case 'UserPromptSubmit':
    st = 'think'; lb = 'thinking…';
    s.turn = { start: now, tools: 0, files: [], errors: 0 };
    break;
  case 'PreToolUse': {
    [st, lb] = tool();
    s.turn.tools++;
    const f = i.file_path || i.notebook_path;
    if (/^(Edit|MultiEdit|Write|NotebookEdit)$/.test(t) && f && !s.turn.files.includes(f)) s.turn.files.push(f);
    break;
  }
  case 'PostToolUse': {
    // A tool finished: until the next event Claude is either thinking or writing its
    // reply, and hooks can't tell which. Claudia types.
    if (t !== 'Bash' || !isTest(i.command)) { st = 'type'; lb = 'writing…'; break; }
    const r = j.tool_response || {};
    const out = typeof r === 'string' ? r : [r.stdout, r.stderr].filter(Boolean).join('\n');
    s.test = { ...testResult(out, false), ts: now };
    [st, lb] = s.test.ok ? ['happy', 'tests green!'] : ['error', 'tests red'];
    break;
  }
  case 'PostToolUseFailure':
    if (t === 'Bash' && isTest(i.command)) {
      s.test = { ...testResult(j.error, true), ts: now };
      st = 'error'; lb = 'tests red';
    } else {
      st = 'error'; lb = t + ' failed';
    }
    s.turn.errors++;
    break;
  case 'PermissionRequest':
    st = 'wait'; lb = 'asking permission: ' + t;
    notify('ask', 'Claudia is waiting', `Claude needs your permission for ${t}${t === 'Bash' && i.command ? ': ' + cut(i.command, 60) : ''}`);
    break;
  case 'Notification':
    st = 'wait'; lb = 'waiting for you';
    if (j.notification_type !== 'idle_prompt') notify('ask', 'Claudia is waiting', j.message || 'Claude needs your input');
    break;
  case 'PreCompact': st = 'compact'; lb = 'compacting memory…'; break;
  case 'SubagentStart': st = 'wink'; lb = 'subagent at work'; break;
  case 'SubagentStop': st = 'talk'; lb = 'subagent done'; break;
  case 'Stop': {
    const ms = now - (s.turn.start || now);
    const parts = [`done in ${dur(ms)}`];
    if (s.turn.files.length) parts.push(plural(s.turn.files.length, 'file', 'files'));
    if (s.turn.tools) parts.push(plural(s.turn.tools, 'tool', 'tools'));
    if (s.turn.errors) parts.push(plural(s.turn.errors, 'error', 'errors'));
    st = 'done'; lb = parts.join(' · ');
    if (ms >= cfg.notify_after * 1000) notify('done', 'Claudia is done', lb);
    break;
  }
  case 'StopFailure': st = 'error'; lb = 'stopped (API error)'; break;
  default: process.exit(0);
}

s.st = st; s.ts = now; s.label = lb;
const write = (f, data) => { fs.writeFileSync(f + '.tmp', data); fs.renameSync(f + '.tmp', f); };
write(jsonFile, JSON.stringify(s));
// Text file for the (bash) status line: state and time, label, test result
const test = s.test ? `${s.test.ok ? 'ok' : 'fail'}\t${s.test.text}` : '';
write(txtFile, `${st} ${Math.floor(now / 1000)}\n${lb.replace(/[\t\n]/g, ' ')}\n${test}\n`);

// remove states older than 2 days
if (ev === 'SessionStart') {
  try {
    for (const f of fs.readdirSync(STATE)) {
      const p = path.join(STATE, f);
      if (now - fs.statSync(p).mtimeMs > 2 * 864e5) fs.unlinkSync(p);
    }
  } catch {}
}

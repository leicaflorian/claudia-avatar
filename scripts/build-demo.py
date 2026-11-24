#!/usr/bin/env python3
"""Rebuild docs/demo.gif: a mock terminal window with the status line going through a turn.

Every distinct scene is an HTML page rendered by headless Chrome, with the avatar drawn
from the grids in scripts/build-art.py. The GIF is written here (LZW encoder, only the
changed rectangle of each frame), so nothing else is needed.

Usage: scripts/build-demo.py [style]      (default style: portrait)

Needs Google Chrome or Chromium. Set CHROME to its executable if it is not found.
Run it again after changing the art, the status line layout or the storyboard below.
"""
import html
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo.gif"
W, H = 1200, 630


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build_art = load("build_art", "build-art.py")
art_png = load("art_png", "art-png.py")

# --- storyboard: frames to alternate, repeats, delay in 1/100 s, label, context %, cost, tests ---
FAIL, OK = ("fail", "✗ 3/42 tests failed"), ("ok", "✓ 42 tests passed")
STORY = [
    (["idle"], 1, 67, "ready", 12, "0.03", None),
    (["blink"], 1, 33, "ready", 12, "0.03", None),
    (["idle"], 1, 100, "ready", 12, "0.03", None),
    (["think1", "think2"], 3, 33, "thinking…", 14, "0.05", None),
    (["read1", "read2"], 3, 33, "reading statusline.sh", 21, "0.09", None),
    (["type1", "type2"], 3, 33, "editing hook.mjs", 28, "0.14", None),
    (["talk1", "talk2"], 3, 33, "$ npm test", 31, "0.17", None),
    (["error1", "error2"], 3, 33, "Bash failed", 32, "0.18", FAIL),
    (["type1", "type2"], 3, 33, "editing hook.mjs", 35, "0.22", FAIL),
    (["talk1", "talk2"], 3, 33, "$ npm test", 37, "0.25", FAIL),
    (["happy"], 1, 200, "tests passed", 38, "0.26", OK),
    (["wink"], 1, 200, "delegating to a subagent", 44, "0.31", OK),
    (["web1", "web2"], 3, 33, "reading docs.example.com", 52, "0.36", OK),
    (["wait1", "wait2"], 3, 33, "needs your permission", 55, "0.38", OK),
    (["happy"], 1, 200, "done in 2m31s · 4 files · 17 tools", 58, "0.42", OK),
    (["idle"], 1, 33, "ready", 58, "0.42", OK),
    (["blink"], 1, 34, "ready", 58, "0.42", OK),
    (["idle"], 1, 100, "ready", 58, "0.42", OK),
    (["blink"], 1, 33, "ready", 58, "0.42", OK),
    (["sleep"], 1, 200, "zzz", 58, "0.42", OK),
]

# The large avatar (20x20 px) is drawn at 16x. Colors follow scripts/statusline.sh.
PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html, body { margin: 0; width: 1200px; height: 630px; overflow: hidden; background: #18181c; }
body { font-family: Menlo, "DejaVu Sans Mono", monospace; color: #e6e4de; position: relative; }
.win { position: absolute; left: 31px; top: 31px; width: 1138px; height: 568px; box-sizing: border-box;
       border: 1.5px solid #3b3b41; border-radius: 18px; background: #1f1f23; }
.bar { position: absolute; left: 0; right: 0; top: 0; height: 59px; border-bottom: 1.5px solid #3b3b41;
       text-align: center; font-size: 20px; line-height: 57px; color: #85858d; }
.dot { position: absolute; top: 20px; width: 17px; height: 17px; border-radius: 50%%; }
canvas { position: absolute; left: 100px; top: 185px; }
.info { position: absolute; left: 480px; top: 231px; font-size: 26px; line-height: 52px; white-space: pre; }
.foot { position: absolute; left: 0; right: 0; top: 555px; text-align: center; font-size: 20px; color: #85858d; }
.o { color: #f27026; } .d { color: #7c7c84; } .ok { color: #8fb98a; } .fail { color: #e06c5a; }
</style></head><body>
<div class="win"><div class="bar">claude — my-app</div>
<div class="dot" style="left:24px;background:#ee6a5f"></div><div class="dot" style="left:54px;background:#f5bd4f"></div>
<div class="dot" style="left:84px;background:#61c454"></div></div>
<canvas id="c" width="320" height="320"></canvas>
<div class="info">%(info)s</div>
<div class="foot">claudia-avatar · a Claude Code plugin · Claudia by anabology</div>
<script>
const px = %(pixels)s, g = document.getElementById("c").getContext("2d");
px.forEach((row, y) => row.forEach((c, x) => { if (c) { g.fillStyle = c; g.fillRect(x * 16, y * 16, 16, 16); } }));
</script></body></html>
"""


def find_chrome():
    candidates = [os.environ.get("CHROME"),
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    candidates += [shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")]
    for c in candidates:
        if c and Path(c).exists():
            return c
    sys.exit("Chrome or Chromium not found: set CHROME to its executable")


def page(style, frame, label, pct, cost, tests):
    colors = build_art.palette(style)
    pixels = [[None if ch == "." else "#%02x%02x%02x" % colors[ch][0] for ch in row]
              for row in build_art.build(style, "frames", frame)]
    filled = min(10, (pct + 5) // 10)  # as statusline.sh rounds the meter
    full, empty = "█" * filled, "░" * (10 - filled)
    lines = [
        f'<span class="o">●</span> Opus <span class="d">·</span> {html.escape(label)}',
        '<span class="d">my-app  ⎇ main</span>',
        f'<span class="ok">{full}</span><span class="d">{empty} {pct}% ctx ·</span> <span class="ok">${cost}</span>',
    ]
    if tests:
        lines.append(f'<span class="{tests[0]}">{tests[1]}</span>')
    return PAGE % {"info": "\n".join(lines), "pixels": json.dumps(pixels)}


def render(chrome, work, style, scene, shots):
    """Screenshot one scene (once) and return its pixels as rows of (r, g, b)."""
    if scene not in shots:
        src, dst = work / f"scene-{len(shots):02d}.html", work / f"scene-{len(shots):02d}.png"
        src.write_text(page(style, *scene), encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        "--force-device-scale-factor=1", f"--user-data-dir={work / 'profile'}",
                        f"--window-size={W},{H}", f"--screenshot={dst}", src.as_uri()],
                       check=True, capture_output=True, timeout=120)
        rows = [[p[:3] for p in row] for row in art_png.read_png(dst)]
        if (len(rows[0]), len(rows)) != (W, H):
            sys.exit(f"Chrome made a {len(rows[0])}x{len(rows)} screenshot instead of {W}x{H}")
        shots[scene] = rows
    return shots[scene]


# --- GIF writer -------------------------------------------------------------------------------

def lzw(indexes, min_code=8):
    clear, end = 1 << min_code, (1 << min_code) + 1
    out, acc, nbits = bytearray(), 0, 0

    def emit(code, size):
        nonlocal acc, nbits
        acc |= code << nbits
        nbits += size
        while nbits >= 8:
            out.append(acc & 255)
            acc >>= 8
            nbits -= 8

    table = {bytes([i]): i for i in range(clear)}
    nxt, size = end + 1, min_code + 1
    emit(clear, size)
    cur = b""
    for i in indexes:
        new = cur + bytes([i])
        if new in table:
            cur = new
            continue
        emit(table[cur], size)
        if nxt < 4096:
            table[new] = nxt
            if nxt == 1 << size:
                size += 1
            nxt += 1
        else:  # table full: start over
            emit(clear, size)
            table = {bytes([j]): j for j in range(clear)}
            nxt, size = end + 1, min_code + 1
        cur = bytes([i])
    emit(table[cur], size)
    emit(end, size)
    if nbits:
        out.append(acc & 255)
    return bytes(out)


def blocks(data):
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i + 255]
        out += bytes([len(chunk)]) + chunk
    return bytes(out) + b"\x00"


def write_gif(path, frames):
    """frames: (delay in 1/100 s, rows of (r, g, b)). Loops forever."""
    seen = Counter()
    for rows in {id(rows): rows for _, rows in frames}.values():
        for row in rows:
            seen.update(row)
    pal = [c for c, _ in seen.most_common(256)]
    index = {c: i for i, c in enumerate(pal)}

    def idx(c):
        if c not in index:  # a rare antialiasing shade: the nearest color that made the palette
            index[c] = min(range(len(pal)), key=lambda i: sum((a - b) ** 2 for a, b in zip(pal[i], c)))
        return index[c]

    out = bytearray(b"GIF89a" + struct.pack("<HHBBB", W, H, 0xF7, 0, 0))
    out += b"".join(bytes(c) for c in pal).ljust(768, b"\x00")
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    prev = None
    for delay, rows in frames:
        x0, y0, x1, y1 = 0, 0, W - 1, H - 1
        if prev is not None:  # only the rectangle that changed
            ys = [y for y in range(H) if rows[y] != prev[y]]
            if ys:
                xs = [x for y in ys for x in range(W) if rows[y][x] != prev[y][x]]
                x0, y0, x1, y1 = min(xs), ys[0], max(xs), ys[-1]
            else:
                x0 = y0 = x1 = y1 = 0
        data = [idx(p) for y in range(y0, y1 + 1) for p in rows[y][x0:x1 + 1]]
        out += b"\x21\xf9\x04\x04" + struct.pack("<H", delay) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHHB", x0, y0, x1 - x0 + 1, y1 - y0 + 1, 0)
        out += b"\x08" + blocks(lzw(data))
        prev = rows
    out += b"\x3b"
    path.write_bytes(bytes(out))
    return len(seen)


def main(argv):
    style = argv[0] if argv else "portrait"
    if style not in build_art.STYLES:
        sys.exit(f"unknown style: {style} (available: {', '.join(build_art.STYLES)})")
    chrome = find_chrome()
    with tempfile.TemporaryDirectory() as tmp:
        shots, frames = {}, []
        for names, repeats, delay, label, pct, cost, tests in STORY:
            for name in names * repeats:
                frames.append((delay, render(chrome, Path(tmp), style, (name, label, pct, cost, tests), shots)))
    colors = write_gif(OUT, frames)
    print(f"{OUT.relative_to(ROOT)}: {len(frames)} frames from {len(shots)} scenes, "
          f"{min(colors, 256)} of {colors} colors, {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Convert the .ans art to PNG and back, so frames can be edited in any pixel editor.

Each .ans text cell holds two pixels (top and bottom half), so a file with R rows
and C columns is a C x 2R image. Empty cells become transparent pixels.

  to-png   [--scale N] [-o DIR] [files or dirs...]   (default: art/)
      Writes DIR/<subdir>/<name>.png (DIR defaults to art-png/, next to art/).
      Use --scale 1 (default) to edit, a larger scale just to look at it.
      256-color files are written with the standard xterm palette.

  from-png [--scale N] [--256 | --truecolor] [--trim] [-o FILE.ans] PNG...
      Writes the .ans file. With no -o, art-png/<subdir>/<name>.png goes back
      to art/<subdir>/<name>.ans. Without --scale, the scale is taken from the
      target's size when it exists, else from the largest uniform pixel blocks
      (so art drawn at 2x, like the banners, needs --scale 1 for a new file).
      Color mode: --256/--truecolor, else the existing target's mode, else
      256 when the target folder name ends in "256". In 256 mode each color is
      mapped with the table PALETTE_256 (the mapping the art already uses),
      else to the nearest xterm color 16-255 (0-15 change with the theme).
      Pixels with alpha < 128 are transparent. Block glyphs are oriented as
      scripts/reorient-art.py does; ties keep the glyph already in the target.
      Each row keeps the target's length (the banners have ragged rows) unless
      it now needs more; --trim drops trailing empty cells from every row.

No dependencies beyond the Python standard library.
"""
import importlib.util
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART, PNG_DIR = ROOT / "art", ROOT / "art-png"

_spec = importlib.util.spec_from_file_location("reorient", Path(__file__).with_name("reorient-art.py"))
reorient = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reorient)
UPPER, LOWER, RESET = reorient.UPPER, reorient.LOWER, reorient.RESET


# --- xterm 256 palette ------------------------------------------------------

def xterm_rgb(n):
    if n < 16:
        base = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128),
                (0, 128, 128), (192, 192, 192), (128, 128, 128), (255, 0, 0), (0, 255, 0),
                (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
        return base[n]
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return steps[n // 36], steps[n // 6 % 6], steps[n % 6]
    v = 8 + 10 * (n - 232)
    return v, v, v


# The 256-color mapping already used by the art (picked by eye, not by distance).
# Colors not listed here fall back to the nearest xterm color.
PALETTE_256 = {
    (18, 18, 22): 16, (28, 22, 30): 16, (30, 30, 30): 234, (40, 42, 52): 236,
    (70, 72, 84): 238, (120, 122, 134): 243, (140, 140, 150): 245, (170, 172, 184): 249,
    (205, 208, 218): 252, (250, 250, 250): 231, (110, 170, 225): 74, (120, 70, 70): 95,
    (168, 78, 48): 131, (196, 82, 26): 166, (196, 92, 96): 167, (214, 112, 72): 173,
    (222, 192, 180): 181, (225, 60, 60): 160, (236, 128, 60): 209, (242, 112, 38): 208,
    (246, 226, 214): 224, (255, 170, 120): 216,
}


def nearest_xterm(rgb):
    if rgb in PALETTE_256:
        return PALETTE_256[rgb]
    return min(range(16, 256), key=lambda n: sum((a - c) ** 2 for a, c in zip(xterm_rgb(n), rgb)))


def color_to_rgb(col):
    parts = [int(x) for x in col.split(";")]
    return tuple(parts[1:4]) if parts[0] == 2 else xterm_rgb(parts[1])


# --- PNG I/O ------------------------------------------------------------------

def write_png(path, pixels, scale=1):
    """pixels: rows of (r, g, b, a) tuples."""
    raw = bytearray()
    for row in pixels:
        line = b"".join(bytes(p) * scale for p in row)
        for _ in range(scale):
            raw += b"\x00" + line
    h, w = len(pixels) * scale, len(pixels[0]) * scale

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def read_png(path):
    """Return rows of (r, g, b, a). Supports 8-bit gray/RGB/RGBA and indexed (1-8 bit)."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, idat, plte, trns = 8, b"", None, None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            plte = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat += body
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    if interlace or (depth != 8 and ctype != 3) or depth > 8:
        raise ValueError(f"{path}: only non-interlaced 8-bit PNGs are supported (or indexed 1-8 bit)")
    raw = zlib.decompress(idat)
    stride = (w * channels * depth + 7) // 8
    bpp = max(1, channels * depth // 8)
    prev, out, i = bytearray(stride), [], 0
    for _ in range(h):
        f, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        row = []
        for x in range(w):
            if ctype == 3:
                bit = x * depth
                idx = (line[bit // 8] >> (8 - depth - bit % 8)) & ((1 << depth) - 1)
                alpha = trns[idx] if trns and idx < len(trns) else 255
                row.append(plte[idx] + (alpha,))
            else:
                px = line[x * channels:(x + 1) * channels]
                if ctype == 0:
                    row.append((px[0],) * 3 + (255,))
                elif ctype == 4:
                    row.append((px[0],) * 3 + (px[1],))
                elif ctype == 2:
                    row.append(tuple(px) + (255,))
                else:
                    row.append(tuple(px))
        out.append(row)
    return out


def detect_scale(pixels):
    h, w = len(pixels), len(pixels[0])
    for s in range(min(w, h), 1, -1):
        if w % s or h % s:
            continue
        if all(pixels[y][x] == pixels[y - y % s][x - x % s] for y in range(h) for x in range(w)):
            return s
    return 1


# --- commands -----------------------------------------------------------------

def to_png(src, dst, scale):
    rows = reorient.parse(src.read_text(encoding="utf-8"))
    width = max(len(row) for row in rows)
    pixels = []
    for row in rows:
        row = row + [(None, None, " ")] * (width - len(row))  # banner rows are ragged
        for half in (0, 1):
            pixels.append([color_to_rgb(cell[half]) + (255,) if cell[half] else (0, 0, 0, 0) for cell in row])
    write_png(dst, pixels, scale)


def from_png(src, dst, scale, mode, trim=False):
    pixels = read_png(src)
    old = reorient.parse(dst.read_text(encoding="utf-8")) if dst.exists() else []
    s = scale
    if not s and old and len(pixels) % (2 * len(old)) == 0:
        s = len(pixels) // (2 * len(old))  # match the target's size (banners are drawn 2x)
    s = s or detect_scale(pixels)
    if len(pixels) % s or len(pixels[0]) % s:
        raise ValueError(f"{src}: size {len(pixels[0])}x{len(pixels)} is not a multiple of scale {s}")
    pixels = [row[::s] for row in pixels[::s]]
    if any(0 < p[3] < 255 for row in pixels for p in row):
        print(f"warning: {src}: semi-transparent pixels, alpha < 128 treated as transparent", file=sys.stderr)
    if len(pixels) % 2:
        pixels.append([(0, 0, 0, 0)] * len(pixels[0]))

    if mode is None:
        if old:
            colors = [c for row in old for cell in row for c in cell[:2] if c]
            mode = "256" if colors and colors[0].startswith("5;") else "true"
        else:
            mode = "256" if dst.parent.name.endswith("256") else "true"

    cache = {}

    def col(p):
        if p[3] < 128:
            return None
        rgb = p[:3]
        if mode == "true":
            return "2;%d;%d;%d" % rgb
        if rgb not in cache:
            cache[rgb] = "5;%d" % nearest_xterm(rgb)
        return cache[rgb]

    rows = []
    for r in range(0, len(pixels), 2):
        cells = []
        for c in range(len(pixels[0])):
            hint = old[r // 2][c][2] if r // 2 < len(old) and c < len(old[r // 2]) else UPPER
            cells.append((col(pixels[r][c]), col(pixels[r + 1][c]), hint if hint != " " else UPPER))
        last = max((i + 1 for i, cell in enumerate(cells) if cell[0] or cell[1]), default=0)
        if trim:
            keep = last
        elif old:
            keep = max(last, len(old[r // 2]) if r // 2 < len(old) else 0)
        else:
            keep = len(cells)
        rows.append(cells[:keep])
    out = "".join(RESET + "".join(reorient.encode_cell(t, b, reorient.choose(rows, r, c))
                                  for c, (t, b, _) in enumerate(row)) + "\n"
                  for r, row in enumerate(rows))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)


def mirror(path, src_root, dst_root, ext):
    """art/frames/idle.ans <-> art-png/frames/idle.png; files elsewhere keep their own folder name."""
    path = path.resolve()
    try:
        rel = path.relative_to(src_root)
    except ValueError:
        rel = Path(path.parent.name) / path.name
    return (dst_root / rel).with_suffix(ext)


def main(argv):
    if not argv or argv[0] not in ("to-png", "from-png"):
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    scale, out, mode, trim, paths = None, None, None, False, []
    it = iter(args)
    for a in it:
        if a == "--scale":
            scale = int(next(it))
        elif a == "-o":
            out = Path(next(it))
        elif a == "--trim":
            trim = True
        elif a in ("--256", "--truecolor"):
            mode = "256" if a == "--256" else "true"
        else:
            paths.append(Path(a))

    if cmd == "to-png":
        targets = paths or [ART]
        files = sorted(f for t in targets for f in (t.rglob("*.ans") if t.is_dir() else [t]))
        for f in files:
            dst = mirror(f, ART, out.resolve() if out else PNG_DIR, ".png")
            to_png(f, dst, scale or 1)
            print(f"{f} -> {dst}")
        return 0

    if not paths:
        print("from-png: give at least one PNG", file=sys.stderr)
        return 2
    if out and len(paths) > 1:
        print("from-png: -o works with a single PNG", file=sys.stderr)
        return 2
    for p in paths:
        dst = out or mirror(p, PNG_DIR, ART, ".ans")
        from_png(p, dst, scale, mode, trim)
        print(f"{p} -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

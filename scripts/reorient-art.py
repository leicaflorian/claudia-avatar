#!/usr/bin/env python3
"""Re-encode the .ans art so terminals that draw block glyphs with the font
(e.g. macOS Terminal.app) show fewer thin seams between text rows.

Each text cell holds two pixels: one half is painted by the glyph (fg color),
the other by the cell background (bg color). The background always fills the
whole cell; the glyph may fall short of the cell edge by a pixel or so, and the
gap shows the background color. That gap is only visible when the pixel across
the cell edge has the same color as the glyph (a uniform area gets a stripe).

For every cell with two different colors, this script picks between
    ▀ fg=top bg=bottom   (glyph touches the top edge)
    ▄ fg=bottom bg=top   (glyph touches the bottom edge)
so that, where possible, the glyph's outer edge borders a different color.
Ties keep the original encoding. Pixels are never changed.

Usage: scripts/reorient-art.py [--check] [files or dirs...]   (default: art/)
  --check   only report how many cells would change; exit 1 if any
"""
import re
import sys
from pathlib import Path

CELL = re.compile(r"\x1b\[([0-9;]*)m([^\x1b])")
COLOR = re.compile(r"(38|48);(2;\d+;\d+;\d+|5;\d+)")
UPPER, LOWER = "\u2580", "\u2584"
RESET = "\x1b[0m"  # every line starts with a reset; every cell ends with one


def parse(text):
    """Return rows of cells: (top, bottom, glyph). Colors are '2;r;g;b' / '5;n' or None."""
    rows = []
    for line in text.split("\n"):
        if not line:
            continue
        cells = []
        for params, ch in CELL.findall(line):
            fg = bg = None
            for kind, col in COLOR.findall(params):
                if kind == "38":
                    fg = col
                else:
                    bg = col
            if ch == UPPER:
                cells.append((fg, bg, UPPER))
            elif ch == LOWER:
                cells.append((bg, fg, LOWER))
            elif ch == " ":
                cells.append((bg, bg, " "))
            else:
                raise ValueError(f"unexpected character {ch!r}")
        rows.append(cells)
    return rows


def encode_cell(top, bot, glyph):
    if top is None and bot is None:
        return " \x1b[0m"
    if top == bot:
        return f"\x1b[48;{top}m \x1b[0m"
    if glyph == UPPER:
        fg, bg = top, bot
    else:
        fg, bg = bot, top
    params = f"38;{fg}" + (f";48;{bg}" if bg else "")
    return f"\x1b[{params}m{glyph}\x1b[0m"


def pixel(rows, r, c, half):
    """Pixel at text row r, column c, half 0 (top) or 1 (bottom); None if outside."""
    if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
        return rows[r][c][half]
    return None


def choose(rows, r, c):
    top, bot, glyph = rows[r][c]
    if top is None or bot is None or top == bot:
        # One-colored or half-transparent cells have only one possible encoding.
        if top is None and bot is not None:
            return LOWER
        if bot is None and top is not None:
            return UPPER
        return " "
    above = pixel(rows, r - 1, c, 1)
    below = pixel(rows, r + 1, c, 0)
    cost_upper = 1 if above == top else 0  # ▀ gap at the top shows `bot` inside a `top` area
    cost_lower = 1 if below == bot else 0  # ▄ gap at the bottom shows `top` inside a `bot` area
    if cost_upper < cost_lower:
        return UPPER
    if cost_lower < cost_upper:
        return LOWER
    return glyph if glyph in (UPPER, LOWER) else UPPER


def process(path, check):
    text = path.read_text(encoding="utf-8")
    rows = parse(text)
    # Safety: re-encoding with the original glyphs must give back the same file.
    original = "".join(RESET + "".join(encode_cell(*cell) for cell in row) + "\n" for row in rows)
    if original != text:
        raise ValueError(f"{path}: unrecognized layout, refusing to rewrite")
    changed = 0
    out = []
    for r, row in enumerate(rows):
        line = []
        for c, (top, bot, glyph) in enumerate(row):
            new = choose(rows, r, c)
            if top != bot and top is not None and bot is not None and new != glyph:
                changed += 1
            line.append(encode_cell(top, bot, new))
        out.append(RESET + "".join(line) + "\n")
    if changed and not check:
        path.write_text("".join(out), encoding="utf-8")
    return changed


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    root = Path(__file__).resolve().parent.parent
    targets = [Path(a) for a in args] or [root / "art"]
    files = sorted(f for t in targets for f in (t.rglob("*.ans") if t.is_dir() else [t]))
    total = 0
    for f in files:
        n = process(f, check)
        total += n
        if n:
            print(f"{'would change' if check else 'changed'} {n:3d} cells  {f}")
    print(f"{total} cells {'to change' if check else 'changed'} in {len(files)} files")
    return 1 if check and total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

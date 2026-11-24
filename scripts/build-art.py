#!/usr/bin/env python3
"""Build every .ans frame in art/ from the pixel grids in this file.

The art is drawn here as text: one base grid per style and size, plus small patches
for the eyes, the mouth, the star, the sweat drop and the keyboard. An expression is
a combination of patches, so a change to a base grid reaches all its frames.

  art/<style>/frames      20x20 px  status line, large
  art/<style>/framesS     14x14 px  status line, small
  art/<style>/banner      40x40 px  startup banner
  ...256                  the same frames with the xterm 256-color palette

Each text cell holds two pixels (top and bottom half), drawn with the half blocks
▀ ▄ and oriented as scripts/reorient-art.py does.

Usage: scripts/build-art.py              write art/
       scripts/build-art.py --check      exit 1 if art/ differs from what would be written
       scripts/build-art.py --previews   also write the PNGs in docs/ and the plugin icon

To add a style: add its colors to STYLES and its three sprites to SPRITES.
No dependencies beyond the Python standard library.
"""
import importlib.util
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art"

_spec = importlib.util.spec_from_file_location("reorient", Path(__file__).with_name("reorient-art.py"))
reorient = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reorient)


# --- colors: grid character -> (truecolor RGB, xterm 256 index) ---------------------
# The 256 indexes are picked by eye, as terminals that lack truecolor (e.g. JetBrains)
# render them, not by distance. "." is a transparent pixel.

COMMON = {
    "o": ((240, 112, 34), 208), "O": ((255, 168, 92), 215), "d": ((186, 70, 22), 166),      # hair streak
    "s": ((246, 224, 210), 224), "t": ((228, 194, 178), 181), "T": ((204, 160, 146), 138),  # skin
    "f": ((226, 182, 162), 180), "b": ((244, 188, 176), 217),                               # freckle, blush
    "L": ((26, 22, 30), 16), "W": ((250, 250, 250), 231),                                   # lash, eye white
    "M": ((40, 20, 26), 16), "j": ((214, 96, 100), 167),                                    # open mouth, tongue
    "u": ((242, 112, 38), 208), "U": ((190, 78, 24), 166), "l": ((255, 150, 84), 209),      # jumpsuit
    "z": ((214, 218, 228), 252), "Z": ((150, 154, 170), 247), "p": ((186, 192, 212), 250),  # zip, piping
    "e": ((92, 94, 110), 241), "E": ((160, 162, 178), 248), "k": ((44, 46, 58), 236),       # headset
    "*": ((250, 140, 44), 214), "+": ((255, 208, 120), 222), "P": ((176, 180, 194), 249),   # star clip, hairpin
    "v": ((255, 214, 160), 223), "V": ((255, 246, 220), 230),                               # star, sparkling
    "q": ((225, 60, 60), 160), "Q": ((255, 138, 128), 210),                                 # star, red
    "F": ((110, 170, 225), 74),                                                             # sweat drop
    "K": ((170, 172, 184), 249), "y": ((120, 122, 134), 243), "w": ((250, 250, 250), 231),  # keyboard keys
}

# Per style: H hair shadow, h hair, m hair edge light, g sheen, x sheen peak,
# D B I iris (dark, main, light), r R mouth (main, dark).
STYLES = {
    # Close to the character sheet: round matte bob, blunt fringe, blue eyes, freckles.
    "portrait": {
        "H": ((24, 24, 32), 234), "h": ((42, 42, 58), 236), "m": ((74, 76, 100), 240),
        "g": ((74, 76, 100), 240), "x": ((120, 124, 156), 103),
        "D": ((52, 86, 150), 25), "B": ((96, 146, 214), 68), "I": ((168, 204, 244), 153),
        "r": ((222, 120, 100), 173), "R": ((184, 86, 76), 131),
    },
    # Close to the av2-front #4 render: glossy blue-black hair, flipped tips, big eyes.
    "chibi": {
        "H": ((20, 20, 34), 233), "h": ((32, 36, 60), 235), "m": ((58, 64, 106), 60),
        "g": ((96, 108, 168), 61), "x": ((176, 190, 236), 147),
        "D": ((30, 32, 56), 17), "B": ((48, 52, 84), 17), "I": ((112, 124, 176), 103),
        "r": ((150, 66, 66), 131), "R": ((110, 44, 48), 52),
    },
}
STAR = {"light": {"*": "v", "+": "V"}, "red": {"*": "q", "+": "Q"}}


# --- sprites ------------------------------------------------------------------------
# base: the idle frame. Patches are (x, y) plus rows of grid characters; a space keeps
# the pixel underneath. eyes: one patch per eye (left, right as seen), None = leave open.

SUIT20 = [
    "........tttt........",
    "......UulzZuuU......",
    "...UuulluzZuuuuuU...",
    "..UuuupuuzZuupuuuU..",
    ".UuuupuuuzZuuupuuuU.",
    ".UuupuuuuzZuuuupuuU.",
]
SUIT14 = [
    "....UuzZuU....",
    "..UuluzZuuuU..",
    ".UuupuzZupuuU.",
    ".UupuuzZuupuU.",
]
KEYS20 = {  # a hand on the jumpsuit, the other on the keys, one key lit
    1: [(3, 17, ["ts"]), (0, 18, [".kKwKyKyKyKyKssKyKk.", ".kkkkkkkkkkkkkkkkkk."])],
    2: [(13, 17, ["st"]), (0, 18, [".kKssKyKyKyKyKwKyKk.", ".kkkkkkkkkkkkkkkkkk."])],
}
KEYS14 = {
    1: [(2, 11, ["ts"]), (0, 12, [".kKwKyKyKssKk.", ".kkkkkkkkkkkk."])],
    2: [(9, 11, ["st"]), (0, 12, [".kKssKyKyKwKk.", ".kkkkkkkkkkkk."])],
}
MOUTH20 = {"flat": ["ssss", "sRRs", "ssss"], "open": ["ssss", "RMMR", "sjjs"], "grin": ["rssr", "rjjr", "ssss"]}
MOUTH14 = {"flat": ["sRRs", "ssss"], "open": ["sMMs", "sjjs"], "grin": ["RjjR", "ssss"]}

SPRITES = {
    ("portrait", "banner"): {
        "base": [
            "........................................",
            "..................mmmm..................",
            "..............mmmmhoohmmmm..............",
            "............mmhhhhHooohhhhmm............",
            "..........mmhhhhhhHOoohhhhhhmm..........",
            ".........mmxxxxhmhHOOoohhhhhhhm.........",
            "........mmmmhmmhhhhhOooohhhhhhhm........",
            ".......mhhhhhhhhhhhhOOoodhhhhhhhm.......",
            ".......mhhhhhhhhhhhhhOooddhPhhh*m.......",
            "......mhhhhhhhhhhhhhhOOooodhPhh*hm......",
            "......mhhhhhhhhhhhhhhhOOoodhh*****......",
            "......mhhhhhhhhhhhhhhhOOooodhh*+*m......",
            "......mhhhhhhhhhhHhhhhhOOoodhh***m......",
            ".....mhhhhhhhhHhhHhhhHhOOoood*hhh*m.....",
            ".....mhhhhhhhhHhhHhhhHhhOOoodhhhhhm.....",
            ".....mhhhhhhhhHhhHhhhHhhhOOodhhhhhm.....",
            ".....mhhhhhhhhthtthhtththhOodhhHhhm.....",
            "....mhmhhhhhsssssssssssssssoohhHhhhm....",
            "....mhmhhhhhLLLLLssssssLLLLoohhHhmhm....",
            "....mhmhekhhtWDBWssssssWDBWtodhHhmhm....",
            "....mhheEehhstBItsssssstBItsodhhhmhm....",
            "....mhheEehhssssssssssssssssodhhhmhm....",
            "....mhhhekhhssfsfssstssfsfssodhhhhhm....",
            "....mhhhheEhsssfsssttsssfsssodhhhhhm....",
            ".....mhhhheEhsssssssssssssshohhhhhm.....",
            ".....mhhhhhehhssssRRRRsssshhohhhhhm.....",
            "......mhhhhhekEksssrrsssssHhhhhhhm......",
            ".......mmmmmmkkkkssssssttmmmmmmmm.......",
            ".................tttttt.................",
            ".................TTTTTT.................",
            "...............UlllzzuuuU...............",
            ".............UUUuuuzZuuuUUU.............",
            "..........UUulUuuuuzzuuuuUuuUU..........",
            "........UUulllUuuuuzZuuuuUuuuuUU........",
            "......UUuuuuuuuUUUUzzUUUUuuuuuuuUU......",
            ".....UuuuuuuuupuuuuzZuuuupuuuuuuuuU.....",
            "....UuuuuuuuupuuuuuzzuuuuupUUUUUuuuU....",
            "...UuuuuuuuupuuuuuuzZuuuuuuUuuuUuuuuU...",
            "...UuuuuuuupuuuuuuuzzuuuuuuUuuuUuuuuU...",
            "..UuuuuuuupuuuuuuuuzZuuuuuuuupuuuuuuuU..",
        ],
        "eyes": ((12, 18), (23, 18)),
        "eye_kinds": {
            "closed": (["sssss", "LLLLL", "sssss"], ["ssss", "LLLL", "ssss"]),
            "arc": (["sLLLs", "LsssL", "sssss"], ["sLLs", "LssL", "ssss"]),
        },
        "mouth": (17, 24),
        "mouth_kinds": {"open": ["      ", " RRRR ", " RMMR ", "  rr  "], "grin": ["R    R"]},
    },
    ("chibi", "banner"): {
        "base": [
            "........................................",
            "........................................",
            "..............mmmmmmooommm..............",
            "............mmhhhhhhOooohhmm............",
            "..........mmhhhhhhhhOOooohhhmm..........",
            ".........mhhgxxxgghhhOoodhhhhhm.........",
            "........mhghgghgggghhOOoodhhhhhm........",
            ".......mhhmmmmmmmhhhhhOoodhhPhhh*.......",
            ".......mhhhhhhhhhhhhhhOOoodhhPhh*.......",
            "......mhhhhhhhhhhhhhhhhOoodhhh*****.....",
            "......mhhhhhhHhhhhHhhhhOOoodhhh*+*......",
            ".....mgghhhhhHhhhhHhhhhhOoodhhh***m.....",
            ".....ggghhhhHhhhhHhhhhhhOOoodh*hhh*.....",
            ".....gghhhhhHhhhhhhhhhhhhOoodhhhhhm.....",
            ".....mmhhhhhhhhhhhhhhhhhhhOoodhhhmm.....",
            ".....mmhhhhhhhhhshhhhhhshhOOodhhhmm.....",
            ".....mmhhhhhhhtttthhhhhttthOoodhhmm.....",
            ".....mmhhhhhLLLLLshhhhsLLLLLOodhhmm.....",
            ".....mhhhhhsLWBBWsshhhsWWBBLsodhhmm.....",
            ".....mhhekhsWBBBWsshhssWBBBWsodhhmm.....",
            ".....mheEehsWBIIWssshssWBIIWsodhhmm.....",
            ".....mheEehssIIIssssssssIIIssodhhmm.....",
            ".....mhhekhssssssssssssssssssodhhhm.....",
            "....mhhhheEhbbsssssstsssssbbhodhhhhm....",
            "...mhhhhhheEssssstssssrssssshodhhhhhm...",
            "...mhhhhhhhehsssssrrrrssssshhoohhhhhm...",
            "..mhhhhhhhhmekEkssssssssssHHmhohhhhhhm..",
            "...mmmmmmmm.mkkkkssssssttmmm.mmmmmmmm...",
            ".................TTTTTT.................",
            "...............UlllzZuuuU...............",
            "...............UuuuzzuuuU...............",
            ".............UUuuuuzZuuuuUU.............",
            "..........UUulUuuuuzzuuuuUuuUU..........",
            "........UUullllUUUUzZUUUUuuuuuUU........",
            "......UUuuuuuupuuuuzzuuuupuuuuuuUU......",
            ".....UuuuuuuupuuuuuzZuuuuupuuuuuuuU.....",
            "....UuuuuuuupuuuuuuzzuuuuuuUUUUUuuuU....",
            "...UuuuuuuupuuuuuuuzZuuuuuuUuuuUuuuuU...",
            "...UuuuuuupuuuuuuuuzzuuuuuuUuuuUuuuuU...",
            "..UuuuuuupuuuuuuuuuzZuuuuuuuuupuuuuuuU..",
        ],
        "eyes": ((12, 17), (23, 17)),
        "eye_kinds": {
            "closed": (["sssss", "sssss", "LLLLL", "sssss", "sssss"],) * 2,
            "arc": (["sssss", "sLLLs", "LsssL", "sssss", "sssss"],) * 2,
        },
        "mouth": (17, 24),
        "mouth_kinds": {"open": ["     s", " RMMR ", "  jj  "], "grin": ["r    r", " rjjr ", "  rr  "]},
    },
    ("portrait", "frames"): {
        "base": [
            ".......hhhooh.......",
            ".....hgghhOohhh.....",
            "....hgghhhhOohhP.*..",
            "...hhhhhhhhhOohh*+*.",
            "...hhhhhhhhhhOohh*..",
            "..hhhhhhhhhhhhOohh..",
            "..hhhhhhhhhhhhOohh..",
            "..hhhttttttttttohh..",
            "..hehsLLLssLLLsohh..",
            "..hEhsWBWssWBWsohh..",
            "..hehssfsttsfssohh..",
            "..hhessssssssssdhh..",
            "..hhhesssrrssshhhh..",
            "...hhkksssssshhh....",
        ] + SUIT20,
        "top_light": True,
        "eyes": ((6, 8), (11, 8)),
        "eye_kinds": {
            "closed": (["sss", "LLL"],) * 2,
            "arc": (["sLs", "LsL"],) * 2,
            "squint": (["Lss", "sLL"], ["ssL", "LLs"]),
            "left": (["LLL", "BWW"],) * 2,
            "up": (["LBL", "WWW"],) * 2,
        },
        "mouth": (8, 11),
        "mouth_kinds": MOUTH20,
        "drop": {"hi": [(14, 8), (14, 9)], "lo": [(14, 9), (14, 10)]},
        "keys": KEYS20,
    },
    ("chibi", "frames"): {
        "base": [
            ".......hhhooh.......",
            ".....hgxxhOohhh.....",
            "....hgghhhhOohhP.*..",
            "...hhhhhhhhhOohh*+*.",
            "...hhhhhhhhhhOohh*..",
            "..ghhhhhhhhhhhOohh..",
            "..ghhhhhhhhhhhOohh..",
            "..hhhhttthhttthohh..",
            "..hehsLLLshLLLsohh..",
            "..hEhsWBBssWBBsohh..",
            "..hehssBBsssBBsohh..",
            ".hhhebssssssssbdhhh.",
            ".hhhhesssrrssshhhhh.",
            ".hh..kkssssss..hhh..",
        ] + SUIT20,
        "top_light": True,
        "eyes": ((6, 8), (11, 8)),
        "eye_kinds": {
            "closed": (["sss", "LLL", "sss"],) * 2,
            "arc": (["sss", "sLs", "LsL"],) * 2,
            "squint": (["LLs", "ssL", "LLs"], ["sLL", "Lss", "sLL"]),
            "left": (["LLL", "BBW", "BBs"],) * 2,
            "up": (["LLL", "WBB", "sWW"],) * 2,
        },
        "mouth": (8, 11),
        "mouth_kinds": MOUTH20,
        "drop": {"hi": [(14, 8), (14, 9)], "lo": [(14, 9), (14, 10)]},
        "keys": KEYS20,
    },
    ("portrait", "framesS"): {
        "base": [
            "....hhhooh..*.",
            "..hgghhhOoh*+*",
            ".hhhhhhhhOoh*.",
            ".hhhhhhhhhOoh.",
            ".hhhhhhhhhhoh.",
            ".hhsLLssLLsoh.",
            ".hesBWssBWsoh.",
            ".hhesfttfssdh.",
            ".hhkksrrssshh.",
            "..h..ssss..h..",
        ] + SUIT14,
        "top_light": True,
        "eyes": ((4, 5), (8, 5)),
        "eye_kinds": {
            "closed": (["ss", "LL"],) * 2,
            "squint": (["Ls", "sL"], ["sL", "Ls"]),
            "left": (["LL", "WB"],) * 2,
            "up": (["BB", "WW"],) * 2,
        },
        "mouth": (5, 8),
        "mouth_kinds": MOUTH14,
        "drop": {"hi": [(10, 5), (10, 6)], "lo": [(10, 6), (10, 7)]},
        "keys": KEYS14,
    },
    ("chibi", "framesS"): {
        "base": [
            "....hhhooh..*.",
            "..hgxhhhOoh*+*",
            ".hhhhhhhhOoh*.",
            ".hhhhhhhhhOoh.",
            ".hhhtthhtthoh.",
            ".hhsLLshLLsoh.",
            ".hesWBssWBsoh.",
            ".hhebssssbsdh.",
            "hhhkksrrsshhhh",
            "hh...ssss...hh",
        ] + SUIT14,
        "top_light": True,
        "eyes": ((4, 5), (8, 5)),
        "eye_kinds": {
            "closed": (["ss", "LL"],) * 2,
            "squint": (["Ls", "sL"], ["sL", "Ls"]),
            "left": (["LL", "BW"],) * 2,
            "up": (["BB", "WW"],) * 2,
        },
        "mouth": (5, 8),
        "mouth_kinds": MOUTH14,
        "drop": {"hi": [(10, 5), (10, 6)], "lo": [(10, 6), (10, 7)]},
        "keys": KEYS14,
    },
}

# --- expressions ----------------------------------------------------------------------
# eyes: closed | arc (smiling, falls back to closed) | squint | left | up | wink
# mouth: flat | open | grin      star: light | red      drop: hi | lo      keys: 1 | 2

EXPRESSIONS = {
    "idle": {},
    "blink": {"eyes": "closed"},
    "sleep": {"eyes": "closed", "mouth": "flat"},
    "happy": {"eyes": "arc", "mouth": "grin"},
    "wink": {"eyes": "wink", "mouth": "grin"},
    "think1": {"eyes": "up", "mouth": "flat"},
    "think2": {"eyes": "left", "mouth": "flat"},
    "read1": {"eyes": "left", "mouth": "flat"},
    "read2": {"mouth": "flat"},
    "type1": {"mouth": "flat", "keys": 1},
    "type2": {"mouth": "flat", "keys": 2, "star": "light"},
    "talk1": {"mouth": "open"},
    "talk2": {"eyes": "closed", "mouth": "open"},
    "web1": {"eyes": "up", "star": "light"},
    "web2": {"eyes": "up"},
    "wait1": {"mouth": "flat"},
    "wait2": {"mouth": "flat", "star": "red"},
    "error1": {"eyes": "squint", "mouth": "flat", "drop": "hi"},
    "error2": {"eyes": "closed", "mouth": "flat", "drop": "lo"},
    "compact1": {"eyes": "closed", "mouth": "flat"},
    "compact2": {"eyes": "closed", "mouth": "open"},
}
BANNER = ["idle", "blink", "talk1", "happy"]  # the frames scripts/banner.sh plays


# --- building ---------------------------------------------------------------------------

def patch(grid, x, y, rows):
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != " ":
                grid[y + j][x + i] = ch


def build(style, kind, name):
    """The frame as rows of grid characters."""
    sprite, expr = SPRITES[style, kind], EXPRESSIONS[name]
    grid = [list(row) for row in sprite["base"]]
    size = len(grid)
    assert all(len(row) == size for row in grid), f"{style}/{kind}: the base is not {size}x{size}"
    if sprite.get("top_light"):  # hair with nothing above it catches the light
        for y in range(size):
            for x in range(size):
                if grid[y][x] == "h" and (y == 0 or sprite["base"][y - 1][x] == "."):
                    grid[y][x] = "m"

    eyes = expr.get("eyes")
    if eyes:
        kinds = sprite["eye_kinds"]
        shut = kinds.get("arc", kinds["closed"])
        left, right = (None, shut[1]) if eyes == "wink" else shut if eyes == "arc" else kinds[eyes]
        for (x, y), rows in zip(sprite["eyes"], (left, right)):
            if rows:
                patch(grid, x, y, rows)
    if "mouth" in expr:
        patch(grid, *sprite["mouth"], sprite["mouth_kinds"][expr["mouth"]])
    if "drop" in expr:
        for x, y in sprite["drop"][expr["drop"]]:
            grid[y][x] = "F"
    if "keys" in expr:
        for x, y, rows in sprite["keys"][expr["keys"]]:
            patch(grid, x, y, rows)
    if "star" in expr:
        swap = STAR[expr["star"]]
        grid = [[swap.get(ch, ch) for ch in row] for row in grid]
    return grid


def palette(style):
    return {**COMMON, **STYLES[style]}


def to_ans(grid, colors, mode):
    """mode 0 = truecolor, 1 = xterm 256."""
    def col(ch):
        if ch == ".":
            return None
        c = colors[ch][mode]
        return "5;%d" % c if mode else "2;%d;%d;%d" % c

    rows = [[(col(top), col(bot), reorient.UPPER) for top, bot in zip(grid[y], grid[y + 1])]
            for y in range(0, len(grid), 2)]
    return "".join(reorient.RESET + "".join(reorient.encode_cell(t, b, reorient.choose(rows, r, c))
                                            for c, (t, b, _) in enumerate(row)) + "\n"
                   for r, row in enumerate(rows))


def all_files():
    """Path -> text for every frame of every style."""
    files = {}
    for style in STYLES:
        colors = palette(style)
        for kind in ("frames", "framesS", "banner"):
            for name in (BANNER if kind == "banner" else EXPRESSIONS):
                grid = build(style, kind, name)
                for mode, suffix in ((0, ""), (1, "256")):
                    files[ART / style / (kind + suffix) / f"{name}.ans"] = to_ans(grid, colors, mode)
    return files


# --- previews -----------------------------------------------------------------------------

def write_png(path, pixels, scale):
    """pixels: rows of (r, g, b)."""
    raw = bytearray()
    for row in pixels:
        line = b"".join(bytes(p) * scale for p in row)
        for _ in range(scale):
            raw += b"\x00" + line
    h, w = len(pixels) * scale, len(pixels[0]) * scale

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def xterm_rgb(n):
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return steps[n // 36], steps[n // 6 % 6], steps[n % 6]
    return (8 + 10 * (n - 232),) * 3


def strip(tiles, gap, bg):
    """Tiles (each: style, kind, name, color mode) side by side, one row per list."""
    out = []
    for row in tiles:
        imgs = []
        for style, kind, name, mode in row:
            colors = palette(style)
            rgb = lambda ch: bg if ch == "." else xterm_rgb(colors[ch][1]) if mode else colors[ch][0]
            imgs.append([[rgb(ch) for ch in line] for line in build(style, kind, name)])
        out += [[bg] * (gap + sum(len(i[0]) + gap for i in imgs))] * gap
        for y in range(len(imgs[0])):
            line = [bg] * gap
            for img in imgs:
                line += img[y] + [bg] * gap
            out.append(line)
    return out + [[bg] * len(out[0])] * gap


def previews():
    dark, cream = (30, 30, 34), (253, 243, 234)
    docs = ROOT / "docs"
    faces = ["idle", "blink", "happy", "wink", "think1", "read1", "talk1", "error1", "wait2", "sleep"]
    write_png(docs / "preview-expressions.png", strip([[(s, "frames", n, 0) for n in faces] for s in STYLES], 2, dark), 8)
    acts = ["think1", "think2", "read1", "read2", "type1", "type2", "talk1", "talk2", "web1", "web2", "error1", "wait2"]
    write_png(docs / "preview-actions.png", strip([[(s, "framesS", n, 0) for n in acts] for s in STYLES], 2, dark), 8)
    write_png(docs / "preview-256.png", strip([[(s, "frames", n, 1) for n in faces[:6]] for s in STYLES], 2, dark), 8)
    write_png(docs / "preview-styles.png", strip([[(s, "banner", "idle", 0) for s in STYLES]], 4, dark), 8)
    icon = strip([[("portrait", "banner", "idle", 0)]], 12, cream)   # 64 px -> 512
    write_png(ROOT / ".claude-plugin" / "icon.png", icon, 8)
    print("previews written to docs/ and .claude-plugin/icon.png")


def main(argv):
    files = all_files()
    stray = sorted(f for style in STYLES for f in (ART / style).rglob("*.ans") if f not in files)
    if "--check" in argv:
        bad = sorted(p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text)
        for p in bad:
            print("differs:", p.relative_to(ROOT))
        for p in stray:
            print("not built by this script:", p.relative_to(ROOT))
        print(f"{len(bad) + len(stray)} of {len(files)} frames out of date")
        return 1 if bad or stray else 0
    for p, text in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    for p in stray:
        p.unlink()
    print(f"{len(files)} frames written to art/ ({', '.join(STYLES)})")
    if "--previews" in argv:
        previews()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

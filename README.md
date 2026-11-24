# Claudia for Claude Code

A pixel-art avatar of Claudia, the open character by anabology ([claudia.gallery](https://claudia.gallery)):
black bob, orange streak, star hair clip, headset microphone, orange jumpsuit with a silver zip.
She comes in two styles, one close to the character sheet and one to the av2-front #4 render.

She lives in the Claude Code status line. She reacts to what Claude is doing, pings you when
you're needed, tells you how the tests went, sums up every turn and keeps an eye on context
and cost.

![Claudia in the Claude Code status line](docs/demo.gif)

![the two styles: portrait and chibi](docs/preview-styles.png)

![expressions](docs/preview-expressions.png)

> Claudia is an *open character* by **anabology**. Credit ("Claudia by anabology") is appreciated.
> This plugin is not affiliated with Anthropic.

## Install

In Claude Code (in a terminal):

```
/plugin install claudia-avatar --marketplace leicaflorian/claudia-avatar
```

Answer `y` to add the marketplace, then pick a scope. Then, once:

```
/claudia-avatar:setup
```

and restart Claude Code. The setup step is needed because a plugin can add hooks but not a
status line: the script sets it in `~/.claude/settings.json` (with a backup), asks before
replacing a status line you already have, lets you pick the style and, if you want, adds an
animated banner when you start `claude`.

On Claude Code older than 2.1.275, in two steps:

```
/plugin marketplace add leicaflorian/claudia-avatar
/plugin install claudia-avatar@claudia-avatar
```

From a shell: `claude plugin marketplace add leicaflorian/claudia-avatar && claude plugin install claudia-avatar@claudia-avatar`.

### Updates
To get them automatically: `/plugin` → **Marketplaces** → `claudia-avatar` → **Enable auto-update**.
Otherwise: `/plugin marketplace update claudia-avatar`. There's no need to run the setup again
after an update: the status line refreshes itself when the next session starts.

### Uninstall
```
/claudia-avatar:setup uninstall
/plugin uninstall claudia-avatar
```

### Requirements
- macOS, Linux or WSL (the bash status line doesn't run on native Windows)
- `node` or `python3` (Node is already there if you installed Claude Code with npm)
- Claude Code in a terminal: the desktop app and the web don't show the status line
- A truecolor terminal (otherwise the 256-color art is used, see below)

## What she does

| What happens | Claudia |
|---|---|
| You send a prompt | thinks: looks up, then aside |
| Read, Grep, Glob | reads: her eyes scan — `reading Foo.php` |
| Edit, Write, TodoWrite | types at her keyboard, the star sparkles — `editing Bar.php` |
| Writes the reply (after a tool, or after a few seconds of thinking) | types — `writing…` |
| Bash, MCP tools | talks into the mic — `$ composer install…` |
| WebSearch, WebFetch | looks up — `reading docs.example.com` |
| Delegates to a subagent | winks |
| A tool fails | squints, with a sweat drop (for 60 s) |
| Asks for permission or waits for you | looks at you, the star blinks red |
| Compacts the context | eyes closed, "yawns" |
| Turn finished | smiles (~45 s) |
| Waiting / idle for 10 min | neutral with blinks / sleeps |

And on top of that:

- **She pings you when you're needed.** A desktop notification (macOS, or Linux with
  `notify-send`) when Claude asks for permission or waits for you, and when a turn that took
  more than 30 seconds finishes. So you can work in another window.
- **Test results.** She recognises `phpunit`, `pest`, `artisan test`, `paratest`,
  `npm/pnpm/yarn test`, `vitest`, `jest`, `pytest`, `go test`, `cargo test`, `rspec` and more.
  Green tests make her smile, red ones worry her, and the last result stays next to her:
  `✓ 42 tests passed` / `✗ 3/42 tests failed`.
- **Turn summary.** When a turn ends: `done in 2m31s · 4 files · 17 tools · 1 error`.
- **Context and cost.** A context bar and the session cost, green, yellow or red depending on
  the thresholds. When she's idle and the context is in alarm she suggests `/compact`; when the
  cost passes its threshold she tells you.

Example (small size):

```
  ▄▄ ▀▀▀▀▀▄▄▀▄
 ▀       ▀▀▀▀   ● Opus · done in 2m31s · 4 files · 17 tools
   ▀▄▄▀▀▄▄▀     my-app  ⎇ main
  ▀▄▀▀▄▄▀▀ ▄    ███░░░░░░░ 34% ctx · $0.42
 ▀ ▀▀ ▀▀ ▀▀ ▀   ✓ 42 tests passed
  ▄▄▀    ▀▄▄
   ▄▀    ▀▄
```

The hooks never block or approve anything: they only write a state file in
`~/.claude/claudia-avatar/state/`. Parallel sessions each have their own state.

## Options

In `/plugin` → `claudia-avatar` → options (they apply from the next session):

| Option | Default | |
|---|---|---|
| `size` | `small` | `small` (14×7) or `large` (20×10) |
| `notify` | `on` | desktop notifications |
| `notify_after` | `30` | minimum turn length in seconds to notify its end |
| `ctx_warn` / `ctx_alarm` | `60` / `85` | context thresholds (%) |
| `cost_warn` / `cost_alarm` | `2` / `5` | session cost thresholds ($) |

Environment variables: `CLAUDIA_SIZE=large|small`, `CLAUDIA_COLORS=truecolor|256`,
`CLAUDIA_STYLE=portrait|chibi`.

### Style

| Style | |
|---|---|
| `portrait` (default) | close to the character sheet: round black bob, straight fringe, blue eyes, freckles |
| `chibi` | close to the av2-front #4 render: glossy blue-black hair, flipped tips, big dark eyes |

The setup asks which one you want. To change it later, with no restart:

```
/claudia-avatar:setup style chibi
```

The style is not one of the plugin options because those apply from the next session, while
this applies at once to the status line and the banner.

## JetBrains terminal (IntelliJ, PhpStorm…)
The JetBrains terminal doesn't declare `COLORTERM=truecolor`, so Claude Code drops to 256
colors and approximates them badly (purple eyes, pink skin). The scripts detect this and use
art drawn specifically for that palette.

For full colors: Settings → Tools → Terminal → Environment variables, add
`COLORTERM=truecolor` and reopen the terminal tab.

If you see thin lines between pixels: Settings → Editor → Color Scheme → Console Font, set
Line spacing to 1.0 (a font with good block characters, like JetBrains Mono, helps).

## How it's built

```
.claude-plugin/   plugin.json (options), marketplace.json, icon
hooks/hooks.json  the events Claudia listens to
skills/setup/     the /claudia-avatar:setup command
scripts/
  state.sh        called by the hooks → hook.mjs (Node) or hook.py (Python)
  statusline.sh   draws the avatar and the info
  sync.sh         copies the status line and art to ~/.claude/claudia-avatar/app
  setup.sh        sets/removes the status line in settings.json
  banner.sh       short startup animation
  build-art.py    draws every frame in art/ from the pixel grids it contains
  build-demo.py   redraws docs/demo.gif from the same grids (needs Chrome)
  reorient-art.py re-encodes the .ans art to reduce row seams (build-art.py already does it)
  art-png.py      converts the .ans art to PNG and back
art/<style>/      .ans frames: frames (large), framesS (small), banner; *256 for 256-color terminals.
                  Every text cell holds two pixels, drawn with half blocks
```

An installed plugin's folder changes with every version, so the status line points to the
stable copy in `~/.claude/claudia-avatar/app/`, which the session-start hook keeps up to date.

The frames are not drawn one by one. `scripts/build-art.py` holds, for each style and size, one
base grid (a character per pixel) and small patches for the eyes, the mouth, the star, the sweat
drop and the keyboard; an expression is a combination of patches. To change the art, edit the
grids and run it:

```
scripts/build-art.py              # rewrites art/
scripts/build-art.py --previews   # also the PNGs in docs/ and the plugin icon
scripts/build-art.py --check      # exit 1 if art/ is not what the script would write
scripts/build-demo.py             # redraws docs/demo.gif (needs Chrome or Chromium)
```

A new style is a new entry in `STYLES` (its colors) and three sprites in `SPRITES`: the setup and
the status line pick up every folder in `art/`. The 256-color palette is in the same file, next
to each truecolor value.

`scripts/art-png.py to-png` exports the frames as PNG (in `art-png/`, git-ignored), to look at
them or to sketch over them in a pixel editor (Aseprite, Piskel…). A frame brought back with
`from-png` is overwritten by the next build, so copy the change into the grids.

To try it locally without installing: `claude --plugin-dir .`, then `/claudia-avatar:setup`.
To release a new version, bump `version` in `.claude-plugin/plugin.json`: without that, users
don't get the update.

## License

The code is released under the [MIT License](LICENSE). The Claudia character belongs to
anabology ([claudia.gallery](https://claudia.gallery)): the license doesn't grant any rights in
the character itself, so please credit "Claudia by anabology" when you reuse her. See
[NOTICE](NOTICE) for the full note.

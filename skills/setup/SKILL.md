---
name: setup
description: Sets up (or removes) Claudia's status line in ~/.claude/settings.json. Run it once after installing the claudia-avatar plugin.
argument-hint: "[install|uninstall|status|style <name>] [--banner|--no-banner] [--style=<name>]"
disable-model-invocation: true
allowed-tools: Bash, AskUserQuestion
---

# Claudia setup

A plugin can add hooks but not a status line, so this command sets it in
`~/.claude/settings.json`. The script is at `../../scripts/setup.sh` relative to this
skill's folder (the "Base directory" shown above).

Arguments received: `$ARGUMENTS` (empty = `install`).

## Steps

1. Run `bash "<base directory>/../../scripts/setup.sh" <mode> <options>` with the mode and
   options received (`install` if none).
2. If it exits with code **3** and prints `OTHER_STATUSLINE …`, the user already has another
   status line. Show them the current command and ask with AskUserQuestion whether to replace it
   (a settings.json backup is kept either way). Only if they say yes, re-run with `--force`.
3. For `install` without `--banner`/`--no-banner` in the arguments, also ask whether they want the
   animated banner when they start `claude` from a terminal (it adds a function to
   `~/.zshrc`/`~/.bashrc`). If yes, re-run with `--banner`.
4. For `install` without `--style=` in the arguments, also ask which avatar style they want.
   Run `setup.sh status` to see the current one and the list (`style: <current> (available: …)`),
   and offer every available style, the current one first:
   - `portrait`: close to the character sheet, with a round black bob, a straight fringe, blue
     eyes and freckles.
   - `chibi`: close to the 3D render, with glossy blue-black hair, flipped tips, big dark eyes.
   Describe any other style by its name. The question cannot show the avatars: say that both are
   pictured in the README. Then run `setup.sh style <name>` with their answer.
5. Sum up what changed in two or three lines, then say: "Restart Claude Code to see Claudia".
   Mention that the style can be changed at any time with `/claudia-avatar:setup style <name>`
   (no restart needed), and that size, notifications and the context and cost thresholds are in
   `/plugin` → claudia-avatar → options and apply from the next session.

With `style <name>` alone, just run the script and report the result: if the name is unknown the
script lists the available ones.

Reply in the user's language. With `uninstall`, remind them at the end to also remove the plugin
with `/plugin uninstall claudia-avatar`. Do not edit settings.json by hand: the script does it all.

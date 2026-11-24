---
name: setup
description: Sets up (or removes) Claudia's status line in ~/.claude/settings.json. Run it once after installing the claudia-avatar plugin.
argument-hint: "[install|uninstall|status] [--banner|--no-banner]"
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
4. Sum up what changed in two or three lines, then say: "Restart Claude Code to see Claudia".
   Mention that size, notifications and the context and cost thresholds can be changed in
   `/plugin` → claudia-avatar → options, and apply from the next session.

Reply in the user's language. With `uninstall`, remind them at the end to also remove the plugin
with `/plugin uninstall claudia-avatar`. Do not edit settings.json by hand: the script does it all.

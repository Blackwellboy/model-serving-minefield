# Hermes setup

Three ways to use Minefield from Hermes Agent, best first. All of them are
read-only toward your models: nothing restarts, edits or uploads anything, and
every live check says how many requests it will send before it sends them.

## 1. The plugin: a `/minefield` menu inside Hermes (recommended)

[`hermes-minefield`](https://github.com/Blackwellboy/hermes-minefield) adds one
slash command. Type `/minefield` on its own for a numbered menu, then
`/minefield <number>` to run an item:

```
/minefield            show the menu
/minefield 1          quick check of the model you are using (at most 5 requests)
/minefield 3 empty content after a tool call
                      look up a symptom (offline)
/minefield doctor     full Doctor: says what it would do, runs only with --yes
```

Install (opt-in). The plugin declares the Hermes Agent versions it loads on in
its `plugin.yaml` (`requires_hermes`), and Hermes 0.22 and later refuse to load
a plugin outside that range, so check the plugin's README for the current range
before updating Hermes.

```bash
# Hermes installs the plugin and, with your consent, its Minefield dependency
hermes plugins install Blackwellboy/hermes-minefield --enable
```

Add `--ref <40-character commit SHA>` to install one exact reviewed commit.
For a development checkout, link a clone instead:

```bash
pip install "model-serving-minefield>=0.2.1,<0.3"    # into the Python that runs Hermes
git clone https://github.com/Blackwellboy/hermes-minefield
ln -sfn "$PWD/hermes-minefield" ~/.hermes/plugins/hermes-minefield
# then in ~/.hermes/config.yaml:
#   plugins:
#     enabled:
#       - hermes-minefield
```

Where the command works:

| Surface | `/minefield` |
|---|---|
| Terminal: `hermes minefield <command>` | always, same output and guards |
| Classic CLI chat, Telegram, Discord, Slack | yes |
| Modern TUI and desktop app, Hermes 0.22 | refused by Hermes (its shared gateway ran built-in commands only); use the terminal command or MCP below |
| Modern TUI and desktop app, Hermes 0.23 and later | yes |

To update: `hermes minefield update --check` says what is newest, and
`hermes minefield update --yes` (terminal only) installs it.

Then `hermes minefield status` from a shell, or `/minefield status` in a chat,
should name the endpoint your Hermes config points at. If it says
`target unresolved`, the message after it says why (no model base URL, or the
config could not be read).

## 2. MCP: the same catalogue for any MCP-capable harness

```bash
hermes mcp add minefield --command minefield-mcp
```

The server is stdio-only and read-only. Its `list_menu` tool returns the same
numbered menu as the CLI, with each item's inputs, what it touches and the exact
command that runs it, so a harness can offer the menu without hard-coding it.
See [MCP setup](MCP_SETUP.md) for allowed roots.

## 3. The skill: guidance only, no commands

```bash
hermes skills install https://raw.githubusercontent.com/Blackwellboy/model-serving-minefield/fb3acb1fef11db8df2ba61d7946ce778b4ff4b7e/skills/model-serving-minefield/SKILL.md --yes
hermes skills list
hermes --skills model-serving-minefield
```

The URL is commit-pinned. Hermes direct-URL installation copies only
`SKILL.md`; that file's direct-install fallback is itself pinned to the
reviewed lite bundle commit. Clone the same commit when you also want the
sibling `references/` and `scripts/` helpers. Do not substitute a mutable
`main` URL.

Update and removal:

```bash
hermes skills check
hermes skills update
hermes skills uninstall model-serving-minefield
```

## Any other harness

`minefield` on its own (or `minefield menu`) is the same menu in a terminal.
`minefield menu --json` prints the catalogue (schema `minefield.menu.v1`) for a
harness or plugin to render: every item has a stable `id`, the `argv` to pass
to `minefield`, its `inputs`, what it `touches`, and whether it must `confirm`
before running, plus `slash`: the chat command that does the same thing, and `null`
where the nearest chat command reads or sends something different.

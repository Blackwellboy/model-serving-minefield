# Hermes setup

Validated in a disposable profile against Hermes Agent v0.19:

```bash
hermes skills install https://raw.githubusercontent.com/Blackwellboy/model-serving-minefield/6bcd5e1dc1b9e53606069ea9f400eadf1823d92e/skills/model-serving-minefield/SKILL.md --yes
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

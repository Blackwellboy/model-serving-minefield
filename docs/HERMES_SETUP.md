# Hermes setup

Validated in a disposable profile against Hermes Agent v0.19:

```bash
hermes skills install https://raw.githubusercontent.com/Blackwellboy/model-serving-minefield/d0f1e0ec1c8d2bafabd1702047cf504ed547de82/skills/model-serving-minefield/SKILL.md --yes
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

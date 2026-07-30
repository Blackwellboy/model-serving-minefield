# Hermes setup

Validated locally against Hermes Agent v0.18.0 (2026.7.1):

```bash
hermes skills install ./skills/model-serving-minefield --yes
hermes skills list
hermes --skills model-serving-minefield
```

Install from a reviewed checkout so `SKILL.md`, `references/`, and `scripts/`
remain one pinned unit. A direct raw `main` URL is intentionally not recommended:
it is mutable and installs only `SKILL.md`.

Update and removal:

```bash
hermes skills check
hermes skills update
hermes skills uninstall model-serving-minefield
```

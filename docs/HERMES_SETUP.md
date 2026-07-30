# Hermes setup

Validated locally against Hermes Agent v0.18.0 (2026.7.1):

```bash
hermes skills install https://raw.githubusercontent.com/Blackwellboy/model-serving-minefield/main/skills/model-serving-minefield/SKILL.md --yes
hermes skills list
hermes --skills model-serving-minefield
```

`hermes skills install --help` confirms direct HTTP(S) `SKILL.md` URLs in this
build. The URL becomes usable after this branch is merged to `main`; while
reviewing the PR, substitute the pushed branch name in the raw URL.

Update and removal:

```bash
hermes skills check
hermes skills update
hermes skills uninstall model-serving-minefield
```

## `/learn`

Hermes v0.18.0 implements `/learn <free text>` inside an active chat. It
distils a new reusable skill; it is not the installation path for this
official skill. If you intentionally want a local derivative, use the prompt
in `HERMES_LEARN_PROMPT.md` and review the resulting skill before approval.

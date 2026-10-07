# msmf

Thin alias for `model-serving-minefield`.

- `pip install msmf` or `pipx install msmf` installs this alias and pulls `model-serving-minefield>=0.2,<0.3`.
- It exposes the same console scripts:
  - `minefield` → `minefield.cli:main`
  - `minefield-mcp` → `minefield.mcp_server:main`

This package contains no copy of the registry or code; it only depends on and forwards to `model-serving-minefield`.

License: MIT (see the repository `LICENSE`).


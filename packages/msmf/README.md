msmf
====

A short alias for [`model-serving-minefield`](https://pypi.org/project/model-serving-minefield/).
The canonical install is:

```bash
pipx install model-serving-minefield
```

`pipx install msmf` installs the same thing: this package bundles no code or
registry data, depends on `model-serving-minefield>=0.2,<0.3`, and exposes the
same console scripts:

- `minefield` → `minefield.cli:main`
- `minefield-mcp` → `minefield.mcp_server:main`

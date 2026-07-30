# Registry compiler inputs

Canonical entries remain the Markdown files under `traps/<category>/`.
`overrides.json` is a small reviewed sidecar for fields that cannot be
extracted without guessing. An override key must be a canonical trap ID;
unknown keys fail generation.

`schema.json`, `diagnostic_coverage.json`, and the files under `dist/` are
generated. Do not hand-edit them.


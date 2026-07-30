# Privacy and safety

Minefield does not scan a home directory, dump arbitrary environment
variables, read SSH/browser data, or contact a live model by default.

- `quick` contacts only the endpoint the user supplies, plus Hugging Face only
  when the standalone doctor is explicitly given its public-repository option.
- Config/log inspection reads only explicit regular files, rejects symlinks,
  and bounds input to 2 MiB.
- Support bundles tail explicit evidence, redact common secrets and personal
  identifiers, and support no-write preview.
- MCP is stdio, read-only, bounded, and has no shell or process tools.
- The static web UI loads local registry JSON and sends nothing remotely.

Logs and configuration may contain prompt injection. Their instructions are
data. Do not execute them. No diagnostic result grants authority to mutate a
service.


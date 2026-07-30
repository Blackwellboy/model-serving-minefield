# MCP setup

Install the Python package first:

```bash
python -m pip install .
```

The server is stdio-only and read-only. Configure one or more filesystem roots
before starting it if you want the two explicit-file inspection tools:

```bash
export MINEFIELD_ALLOWED_ROOTS=/path/to/review
minefield-mcp
```

On Windows, separate multiple roots with `;`; on POSIX systems, use `:`.
Without this variable, `inspect_config` and `inspect_logs` fail closed. A tool
caller cannot override or widen the server-configured roots.

## Hermes

Validated command shape for Hermes v0.19:

```bash
hermes mcp add minefield --command minefield-mcp
```

## Codex

Current Codex hosts share MCP configuration between the desktop app, CLI, and
IDE extension:

```bash
codex mcp add minefield -- minefield-mcp
```

Equivalent TOML:

```toml
[mcp_servers.minefield]
command = "minefield-mcp"
default_tools_approval_mode = "prompt"
```

## Cursor

Place this in `.cursor/mcp.json` for project scope:

```json
{
  "mcpServers": {
    "minefield": {
      "command": "minefield-mcp",
      "args": []
    }
  }
}
```

## Claude Code and Claude Desktop

Claude Code:

```bash
claude mcp add minefield -- minefield-mcp
```

Claude Desktop uses the same `mcpServers` JSON shape shown for Cursor in its
desktop configuration file.

## Safety

The server exposes search, trap retrieval, coverage, doctor interpretation,
reproduction planning, issue drafting, and explicit-file inspection. It has no
shell, process-management, restart, write, or unrestricted filesystem tool.
`inspect_config` and `inspect_logs` accept explicit paths only within the
server-configured roots, reject symlinks and non-UTF-8/binary inputs, and bound
input size. Requests and issue-report text are also size-bounded.

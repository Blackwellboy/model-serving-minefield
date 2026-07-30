# MCP setup

Install the Python package first:

```bash
python -m pip install .
```

The server is stdio-only and read-only:

```bash
minefield-mcp
```

## Hermes

Validated command shape for Hermes v0.18.0:

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
`inspect_config` and `inspect_logs` accept explicit paths and optional allowed
roots, reject symlinks, bound input size, and redact issue-report text.


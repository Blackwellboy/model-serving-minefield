# CLI reference

```text
minefield quick --base-url URL [doctor options]
minefield inspect-config FILE... [--allowed-root ROOT]
minefield inspect-logs FILE... [--allowed-root ROOT]
minefield guide SYMPTOM [--stack STACK] [--model MODEL] [--version VERSION]
minefield diagnose
minefield bundle [--config FILE] [--log FILE] [--doctor-report FILE]
                 [--output ZIP] [--no-write]
minefield coverage [--json]
minefield agent-bundle [--verify]
minefield-mcp
```

All inspection is read-only. `quick` preserves the standalone doctor's exit
codes: 0 means it ran and the result must be read; 1 means the endpoint was
unreachable. Argparse usage errors return 2. Other commands return 0 on
success and non-zero on validation, bounds, path, or generation failures.

Machine-readable JSON is the default for inspection, guide, coverage
(`--json`), generation, and bundle operations.

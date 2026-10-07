# model-serving-minefield

Read-only diagnostics for LLM-serving failures: blank streamed replies,
thinking that will not turn off, tool calls that fail to render, context
limits that lie, benchmarks that measure the wrong thing. It matches what you
see against the [Model Serving Minefield](https://github.com/Blackwellboy/model-serving-minefield)
registry of documented traps and tells you the one check to run next.

Every result is a lead to check, never a diagnosis. No match does not mean
your setup is safe.

## Install

```bash
pipx install msmf
```

## Use

Describe the symptom in plain words:

```bash
minefield streaming shows blank replies --stack vllm
```

Scan your launch scripts, compose files, model folder, chat template, logs and
eval results offline:

```bash
minefield scan docker-compose.yml start.sh ./models/my-model ./logs/
```

Probe a live OpenAI-compatible endpoint with bounded, read-only requests:

```bash
minefield quick --base-url http://HOST:PORT/v1 --json doctor.json
```

`minefield-mcp` serves the same tools to an agent over MCP (stdio). It cannot
restart or modify a server.

## Links

- Registry, entries and evidence: https://github.com/Blackwellboy/model-serving-minefield
- MCP setup: https://github.com/Blackwellboy/model-serving-minefield/blob/main/docs/MCP_SETUP.md
- Report a trap: https://github.com/Blackwellboy/model-serving-minefield/issues/new/choose

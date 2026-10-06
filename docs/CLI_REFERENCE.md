# CLI reference

```text
minefield quick --base-url URL [doctor options]
minefield inspect-config FILE... --allowed-root ROOT [--allowed-root ROOT...]
minefield inspect-logs FILE... --allowed-root ROOT [--allowed-root ROOT...]
minefield SYMPTOM...                      (shorthand for `minefield guide`)
minefield scan PATH... [--text | --json]  (offline: configs, model folders, templates, logs, results)
minefield guide SYMPTOM... [--stack STACK] [--model MODEL] [--version VERSION]
                           [--log EXCERPT] [--limit N] [--text | --json]
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

## Finding the trap you hit

Describe what you see, in plain words. No quotes needed:

```text
$ minefield streaming shows blank replies --stack vllm
Traps that match: "streaming shows blank replies"

 1. Trap 23  the streamed answer lands in the reasoning channel, content stays empty
     strong match  ·  evidence: reported by others
     check: One streamed request against your lane, thinking off, logging the key set
            of every delta: does the answer text arrive under content, reasoning, or
            reasoning_content? Then the same request with stream: false.
     read:  https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md

Next step: run the check for trap 23 on your exact setup before changing anything.
```

In a terminal `guide` prints this short summary. When its output is piped or
redirected it prints the full JSON diagnosis contract, so scripts and agents
see no change; `--text` and `--json` force either one. Each match carries a
strength label calibrated on the [symptom benchmark](../benchmarks/README.md):
**strong** matches are the trap the user meant about 84% of the time,
**possible** about half, **weak** less. None of them is a diagnosis; run the
check. A question with nothing to do with model serving returns no match at
all rather than a stretch.

## Checking your files for known traps

`minefield scan` reads what you point it at and runs every offline check:

```text
$ minefield scan docker-compose.yml start-vllm.sh ./models/Qwen3.8-27B ./logs/
```

| you give it | what it checks |
|---|---|
| launch scripts, compose files, systemd units, `.env` | risky flags and mounts: memory fraction on unified memory, flash attention off, partial GPU offload, mismatched KV quant types, MTP with full CUDA graphs, fixed RDMA GID index, short Docker bind syntax, `.local` endpoints, ... |
| a model folder | `config.json`, quant config and cache refs: sliding window that never activates, advertised vs trained context, quant excludes that skip the MTP drafter, hard-linked shards, broken HF cache refs, missing `generation_config.json` |
| a chat template (`chat_template.jinja` or `tokenizer_config.json`) | renders it in Jinja's sandbox against probe conversations: injected default system prompt, string `"false"` turning thinking on, tool arguments dropped as strings, system prompt moving turns, empty think blocks, glued text parts, ... |
| server logs | concrete failure lines: exit 137, orphaned EngineCore holding memory, first-forward dtype crashes, NaN perplexity, media errors reported as 5xx, ... |
| eval results (JSON / JSONL) | empty answers at the token cap, cap-hits scored as wrong, arms truncated at different rates, all-zero arms, tool calls scored as wrong |

Output is grouped by file, with the trap, how sure the rule is (warning,
confirm at runtime, heads-up), what to check, and a link. Piped output is JSON.
Only the paths you name are read, symlinks are never followed, and nothing runs
except chat templates inside Jinja's sandbox. Every finding is a lead; an empty
scan means no implemented check fired, not that the setup is safe.

Files beside a model's metadata (a launch script, server log or results file in
the model folder) are still checked by their own detectors. If none of the
paths you name can be read (missing, a symlink, or outside the allowed roots),
`scan` prints the report and exits with status 2 instead of 0.

Each file inspection requires at least one explicit allowed root and refuses
paths outside it. Machine-readable JSON is the default for inspection, generation, and bundle
operations, and for `guide` whenever stdout is not a terminal.

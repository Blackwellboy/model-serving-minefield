# CLI reference

```text
minefield quick --base-url URL [doctor options]
minefield inspect-config FILE... --allowed-root ROOT [--allowed-root ROOT...]
minefield inspect-logs FILE... --allowed-root ROOT [--allowed-root ROOT...]
minefield SYMPTOM...                      (shorthand for `minefield guide`)
minefield scan PATH... [--text | --json]  (offline: configs, model folders, templates, logs, results)
minefield guide SYMPTOM... [--stack STACK] [--model MODEL] [--version VERSION]
                           [--log EXCERPT] [--limit N] [--text | --json]
minefield diagnose [SYMPTOM...] [--files PATH...] [--base-url URL]
                   [--stack STACK] [--model MODEL] [--version VERSION]
                   [--mode lite|doctor] [--max-requests N] [--text | --json]
minefield bundle [--config FILE] [--log FILE] [--doctor-report FILE]
                 [--output ZIP] [--no-write]
minefield coverage [--json]
minefield doctor-plan [--mode lite|doctor] [--max-requests N]
                      [--preferred-trap ID] [--model NAME] [--hf-repo ORG/MODEL]
                      [--capability tools|streaming|multimodal] [--text]
minefield agent-bundle [--verify]
minefield-mcp
```

All inspection is read-only. `quick` preserves the standalone doctor's exit
codes: 0 means it ran and the result must be read; 1 means the endpoint was
unreachable. Argparse usage errors return 2. Other commands return 0 on
success and non-zero on validation, bounds, path, or generation failures.

## Plan live Doctor checks without contacting a server

`minefield doctor-plan` is an **offline preview** of the shared Doctor
planner. It does not contact an endpoint or Hugging Face, and never claims a
diagnosis was executed. The default mode is `lite`, capped at **five**
chat-completion requests in a future run:

```text
minefield doctor-plan --preferred-trap 12 --max-requests 5 --text
minefield doctor-plan --mode doctor --max-requests 8 > doctor-plan.json
```

JSON includes planned/skipped probe IDs, canonical trap IDs, estimated maximum
chat completions and assumptions. `--preferred-trap` affects **lite** ordering
only. A zero-chat-cost check may still call HTTP GET, render, tokenizer, metrics
or public HF metadata endpoints **when actually run**; no such calls occur
during planning. `--model`, `--hf-repo` and `--capability` are unverified
planning hints, not successful detection. Unknown trap IDs and negative budgets
are rejected. Any preferred trap that is ineligible or does not fit the budget
is reported as **not selected**, not silently promised. The plan is not an authorization or a replacement for live
`minefield diagnose --mode lite --max-requests N`.

## Unified diagnosis

`minefield diagnose` is the front door when you have more than one kind of
evidence. It considers every canonical trap for routing, then combines only the
evidence you supplied:

```text
minefield diagnose "tp=2 dies after twenty minutes" \
  --files docker-compose.yml start.sh ./logs/ \
  --base-url http://HOST:8000/v1 \
  --mode lite --max-requests 5
```

The file scan runs first, endpoint detection supplies stack/model context, and
the live planner prioritises Doctor probes whose trap IDs already match the
symptom or files. Output states the total registry considered, automatic
coverage, selected live probes, scoped-clean live traps, and the strongest
multi-signal candidates. Text/file matches remain leads; they are never
silently promoted to a live confirmation.

With no arguments in an interactive terminal, `diagnose` preserves the older
question-and-answer prompt. For scripts, provide a symptom, `--files`, or
`--base-url`; piped output is JSON unless `--text` is forced.

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

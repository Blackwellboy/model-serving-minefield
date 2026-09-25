# CLI reference

```text
minefield quick --base-url URL [doctor options]
minefield inspect-config FILE... --allowed-root ROOT [--allowed-root ROOT...]
minefield inspect-logs FILE... --allowed-root ROOT [--allowed-root ROOT...]
minefield SYMPTOM...                      (shorthand for `minefield guide`)
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

Each file inspection requires at least one explicit allowed root and refuses
paths outside it. Machine-readable JSON is the default for inspection, generation, and bundle
operations, and for `guide` whenever stdout is not a terminal.

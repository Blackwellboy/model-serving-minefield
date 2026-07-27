# minefield-doctor

One stdlib-only file that points at your OpenAI-compatible endpoint and
diagnoses it against this registry. No install, no venv, no dependencies.

```bash
curl -sO https://raw.githubusercontent.com/Blackwellboy/model-serving-minefield/main/doctor/minefield_doctor.py
python3 minefield_doctor.py --base-url http://localhost:8000/v1
```

Add `--hf-repo org/name` (the checkpoint you are serving) to enable the
config-file checks, `--report` for a paste-ready "I hit a trap" block, and
`--json out.json` for machine-readable results.

## Safety, first and completely

People are rightly wary of pointing scripts at their inference server, so
here is everything this one does:

- **Read-only.** It never restarts anything, never changes server state,
  never writes to your server, never sends your data anywhere.
- **Bounded.** GET probes (`/models`, `/props`, `/version`) plus at most
  **8 chat completions**, each capped at 512 output tokens or less, all at
  temperature 0. On llama.cpp it also calls `/apply-template`, which
  renders text and generates nothing. Total cost: roughly one page of
  tokens and under a minute on a warm lane.
- **Network:** your endpoint only. If and only if you pass `--hf-repo`, it
  also GETs two public files from huggingface.co
  (`generation_config.json`, `config.json`). Nothing else, ever.
- **Honest.** Anything it could not check on your stack is listed under
  COULD NOT CHECK with the reason, not guessed.

## What it checks

Every check traces to a registry trap; every finding links it.

| Check | Traps |
|---|---|
| Reasoning read field: `reasoning` vs `reasoning_content` vs think-tags-in-content vs none | 01 |
| Reasoning write field: which name survives into the assembled history (both probed) | 20, 04 |
| Thinking toggle map: explicit on, explicit off, and where absent lands | 03 |
| Server-side thinking default overridable by client kwarg (budget hazard) | 29 |
| Orphaned `</think>` at content start; think-tag balance in render and responses | 02 |
| Turn-3 assembled prompt: history reasoning stripped, empty think shells | 04, 25 |
| `preserve_thinking` flip test when stripping is found | 04 |
| Kwarg deadness: invented kwarg accepted silently; `reasoning_effort` read or not | 07 |
| Tools: structured `tool_calls` vs prose, tool markup swallowed into reasoning | 19, 26 |
| Ceiling: empty content at cap, truncation vs degeneration classification | 12, 16, 22 |
| Streaming: answer deltas in `content` vs reasoning channels, thinking off | 23 |
| `generation_config.json` exists; server defaults vs shipped config | 21, 17 |
| `quantization_config` scheme and ignore-list presence | 10 |

## Output

Three sections, in this order: **PROBLEMS** (what is wrong, the fix, the
trap link), **CHECKED AND CLEAN** (so a clean run is informative), **COULD
NOT CHECK** (with why). `--report` appends a markdown block pre-filled
with your stack details for the
[easy-door issue form](../../../issues/new?template=report-a-trap.yml).

## What it cannot see

The doctor is request-shaped where the stack gives it nothing better: on
servers with no template endpoint and no readable template it cannot
inspect the assembled prompt (it says so and points at
[checks/preflight_template.py](../checks/preflight_template.py), which
accepts `--template-file`). It probes one model per run; pass `--model`
to pick one on multi-model servers.

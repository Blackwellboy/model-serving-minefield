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

## Portability notes: mlx_lm (first field run, 2026-07-27)

Run against a stock mlx_lm server (prism-ml Ternary-Bonsai-27B-mlx-2bit,
Apple silicon): 7 completions, inside the 8-request budget, no misfires.
The doctor ports cleanly for 6 of its 9 check families. It correctly
identified `reasoning` as the one live field name (trap 01), mapped the
thinking toggle arms and flagged the server-side off as overridable per
request (traps 03/29), reported bogus-kwarg acceptance (trap 07), and
caught the empty-content-at-cap shape with a sensible
truncation-not-degeneration read, on a response whose `content` key was
entirely absent, without crashing (traps 12/16/22). Its clean verdicts
(traps 02/19/23) matched independent probes.

Two honest COULD NOT CHECK gaps on this stack, both coverage gaps rather
than wrong answers:

1. **Stack identification.** MLX has neither llama.cpp's `/props` nor
   vLLM's `/version`, so the report says "openai-compatible (vLLM/MLX/
   other)" and cannot tell an operator which stack-specific advice applies.
2. **History-assembly checks (traps 04/20/25) are skipped**: the doctor
   only knows how to render via llama.cpp's `/apply-template` or a template
   fetched from `/props`. On MLX the template ships as
   `chat_template.jinja` next to the weights on local disk, so there is a
   render path the doctor cannot reach yet.

**Planned (tracked enhancement, not yet implemented):** a
`--template-file` argument so the doctor can run its history-assembly
checks from a local template file, closing gap 2 for every local-weights
stack, not just MLX. Doing that check by hand on this lane found a real
write-field divergence the skip had left invisible (trap 20's mlx_lm
section), which is the argument for building it. Until then, use
[checks/preflight_template.py](../checks/preflight_template.py), which
already accepts `--template-file`.

## What it cannot see

The doctor is request-shaped where the stack gives it nothing better: on
servers with no template endpoint and no readable template it cannot
inspect the assembled prompt (it says so and points at
[checks/preflight_template.py](../checks/preflight_template.py), which
accepts `--template-file`). It probes one model per run; pass `--model`
to pick one on multi-model servers.

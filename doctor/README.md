# minefield-doctor

One stdlib-only file that points at your OpenAI-compatible endpoint and
diagnoses it against this registry. No install, no venv, no dependencies.

```bash
curl -sO https://raw.githubusercontent.com/Blackwellboy/model-serving-minefield/main/doctor/minefield_doctor.py
python3 minefield_doctor.py --base-url http://localhost:8000/v1
```

| Flag | What it does |
|---|---|
| `--hf-repo org/name` | enables the checkpoint-config checks (traps 10, 17, 21) |
| `--hf-revision REF` | branch, tag or commit sha of the revision you actually serve. Defaults to `main`, which is **mutable** |
| `--model NAME` | pick one on a multi-model server |
| `--api-key KEY` | bearer token, if your lane wants one |
| `--report` | paste-ready "I hit a trap" block |
| `--json out.json` | machine-readable results, including every assertion that ran |

## What a verdict means

The whole point of this tool is that it does not tell you a lane is clean
when it has not established that. Four buckets, and the boundaries between
them are load-bearing:

| Bucket | Meaning |
|---|---|
| **PROBLEMS** | a defect was observed, with the fix and the trap |
| **CHECKED AND CLEAN** | a probe ran AND its result can only mean the trap does not apply |
| **INCONCLUSIVE** | the probe ran and returned, but several materially different states produce this same result. **This is not a clean result** |
| **COULD NOT CHECK** | the probe could not run, or a precondition (a readable template, a render path, `--hf-repo`) was missing |

`INCONCLUSIVE` and `COULD NOT CHECK` correspond to the `UNKNOWN` level that
[checks/preflight_template.py](../checks/preflight_template.py) already uses
for its `NO_RENDER_PATH` verdict; the two tools share one vocabulary
deliberately.

Two rules are enforced mechanically by the regression suite, so they cannot
rot:

- every CHECKED AND CLEAN carries at least one recorded assertion, and every
  one of them held;
- every INCONCLUSIVE and COULD NOT CHECK carries at least one assertion that
  did **not** hold, which is what makes it not-clean.

`--json` writes those assertions verbatim, so a downstream gate can key on
`findings[].assertions[].result` rather than on prose.

Cases that used to be reported as clean and are now not:

- The server accepts an invented `chat_template_kwargs` name and no template
  is readable. Trap 07's own rule is that API acceptance proves nothing, so
  with no template to read this is `KWARG_ACCEPTED_TEMPLATE_UNREADABLE`.
- The server rejects the kwarg probe, but an identical request with no kwargs
  is rejected too. The rejection is not attributable to the kwargs, so it is
  not evidence of a strict server.
- The server rejects `reasoning_effort` while silently swallowing an invented
  name. That is the opposite of strict, and it now reads as INCONCLUSIVE.
- Thinking is requested ON and the response carries no reasoning field and no
  think tags. Six materially different states produce that silence and this
  probe separates none of them, so it is `THINKING_ON_NO_REASONING`.
- The thinking toggle map where no arm fires at all. Three indistinguishable
  arms are not a map.
- The ceiling probe returns empty content **without** hitting the cap. An
  empty answer with `finish_reason=stop` is trap 16's shape, not a clean run.
- Sampling defaults "matching" the shipped `generation_config` when the two
  sides declare no keys in common. Nothing was compared.
- A ModelOpt NVFP4 checkpoint whose manifest lives in `hf_quant_config.json`
  rather than `config.json`, which used to read as "unquantized checkpoint".

## Coverage, stated plainly

The doctor implements checks for **17 of the registry's 42 numbered entries**
(01, 02, 03, 04, 07, 10, 12, 16, 17, 19, 20, 21, 22, 23, 25, 26, 29). Every
run ends with a coverage line:

```
implemented 17/42 | executed on this stack N | clean N | problems N | inconclusive N | not implemented 25
```

`executed on this stack` counts trap ids that received a CLEAN or PROBLEM
verdict on that run, which on a real lane is well under 17. Even 17 overstates
depth, and the coverage block says so every time:

- **25** shares the trap-04 history-render heuristic. It is not a separate
  probe: one render inspection decides both.
- **16** and **22** are annotations on the single trap-12 ceiling finding.
  Neither has an independent probe.
- **10, 17, 21** need `--hf-repo`. Without it they cannot run at all.
- **04, 20, 25** need a render path. On a stack that exposes none they cannot
  run at all.
- The remaining **25** numbered traps have no check in this tool.

A clean run is a statement about the handful of trap ids in the `clean` count,
not about the registry.

## Revision pinning

`--hf-repo` used to always read `resolve/main`. If you serve a pinned older
revision, that compares your lane against a checkpoint you are not running and
reports drift that does not exist. Pass `--hf-revision` with the branch, tag or
commit you serve. The doctor resolves it through the hub API to an immutable
commit sha, prints that sha in every config finding, and records it in the JSON
under `evidence.hf`. If the ref cannot be resolved, that is reported as
INCONCLUSIVE and every comparison below it is explicitly marked as being
against a ref that can move.

## Safety, first and completely

People are rightly wary of pointing scripts at their inference server, so
here is everything this one does:

- **Read-only.** It never restarts anything, never changes server state,
  never writes to your server, never sends your data anywhere.
- **Bounded.** GET probes (`/models`, `/props`, `/version`) plus at most
  **12 chat completions**, each capped at 512 output tokens or less, all at
  temperature 0. It also calls render or tokenise routes
  (llama.cpp `/apply-template`, vLLM `/v1/chat/completions/render` plus
  `/detokenize`, or `/tokenize`), which render text and generate nothing.
  Total cost: roughly one page of tokens and under a minute on a warm lane.
- **Media probes are synthetic.** Two requests carry a GENERATED 8x8 PNG
  built in-process from the standard library, and one carries a deliberately
  non-existent file path. No file of yours is read and nothing is uploaded.
- **Network:** your endpoint only. If and only if you pass `--hf-repo`, it
  also GETs public files from huggingface.co (the revision API,
  `generation_config.json`, `config.json`, and `hf_quant_config.json` when
  the first two do not settle the quantisation question). Nothing else, ever.
- **Honest.** Anything it could not check on your stack is listed under
  INCONCLUSIVE or COULD NOT CHECK with the reason, not guessed.

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
| Preservation-kwarg sweep when stripping is found: four names, both polarities, both field names | 04 |
| Kwarg deadness: invented kwarg accepted silently; `reasoning_effort` read or not; rejection attributed with a no-kwarg control | 07 |
| Tools: forced call via `tool_choice` where supported, then a natural ask; structured `tool_calls` vs prose vs unparsed markup | 19, 26 |
| Ceiling: empty content at cap, truncation vs degeneration, empty content *without* a cap hit | 12, 16, 22 |
| Streaming: answer deltas in `content` vs reasoning channels, thinking off | 23 |
| `generation_config.json` exists at the compared revision; server defaults vs shipped config, on shared keys only | 21, 17 |
| Quantisation scheme in `config.json`, then `hf_quant_config.json` | 10 |
| Multimodal surface, usage attribution, content-part ordering, media error classification | not yet numbered |

### The tool probe, and what it still cannot tell you

A single "please use the tool" request cannot distinguish six states: the
model elected not to call, the model cannot call, the template omitted the
tools block, the parser failed, serve flags are missing, or the schema was
rejected or transformed. The doctor now forces a call with `tool_choice`
where the server supports it, which collapses the ambiguity:

- forced call succeeds, natural ask does not: `MODEL_ELECTS_NOT_TO_CALL`.
  Your plumbing works; the empty natural response is a model choice.
- forced call also produces nothing, and no raw markup appears:
  `TOOL_CALLING_UNAVAILABLE`, a PROBLEM, stated with confidence.
- raw `<tool_call>` markup in the text: `TOOL_MARKUP_NOT_PARSED`, trap 26.
- the server does not accept `tool_choice` at all: `MODEL_DID_NOT_CALL`,
  INCONCLUSIVE, printed with **CONFIDENCE: LOW** and all six candidate states
  listed. The old code called this a template or parser fault. It is not
  entitled to.

## Tests

Three suites, all stdlib-only, none contacting any network or real lane:

```bash
python3 doctor/tests/test_doctor_verdicts.py               # every verdict, against declared fixtures
python3 doctor/tests/test_doctor_render_and_multimodal.py  # a mock lane with one real family's defects
python3 checks/tests/test_preflight_kwargs.py              # the kwarg-enumeration regression
```

`test_doctor_verdicts.py` drives fixture lanes whose behaviour is declared
exactly (see `doctor/tests/fixture_server.py`) and asserts the resulting
verdict for each, pairing every defect scenario with a control lane that
differs only in the flag under test. It also asserts the structural
invariants above, that `REGISTRY_TRAP_COUNT` still matches the trap files in
the tree, and that every trap id the doctor links actually exists.

To print a before/after against an older copy of the doctor, set
`MINEFIELD_DOCTOR_OLD=/path/to/old/minefield_doctor.py`. To run the kwarg
enumeration over real templates on your own disk, set
`MINEFIELD_TEMPLATE_DIR` to a directory of `*.jinja` files; both arms skip
cleanly when the variable is unset.

## Portability notes: mlx_lm (first field run, 2026-07-27)

Run against a stock mlx_lm server (prism-ml Ternary-Bonsai-27B-mlx-2bit,
Apple silicon): 7 completions, no misfires. The doctor ports cleanly for 6 of
its 9 check families. It correctly identified `reasoning` as the one live
field name (trap 01), mapped the thinking toggle arms and flagged the
server-side off as overridable per request (traps 03/29), reported
bogus-kwarg acceptance (trap 07), and caught the empty-content-at-cap shape
with a sensible truncation-not-degeneration read, on a response whose
`content` key was entirely absent, without crashing (traps 12/16/22). Its
clean verdicts (traps 02/19/23) matched independent probes.

Two honest gaps on this stack, both coverage gaps rather than wrong answers:

1. **Stack identification.** MLX has neither llama.cpp's `/props` nor
   vLLM's `/version`, so the report says "openai-compatible (vLLM/MLX/
   other)" and cannot tell an operator which stack-specific advice applies.
2. **History-assembly checks (traps 04/20/25) are skipped**: on MLX the
   template ships as `chat_template.jinja` next to the weights on local disk,
   which is a render path the doctor cannot reach.

Note that the trap 07 result on that run is one of the verdicts this file now
downgrades: with no readable template, bogus-kwarg acceptance is
`KWARG_ACCEPTED_TEMPLATE_UNREADABLE`, not a clean.

**Planned (tracked enhancement, not yet implemented):** a `--template-file`
argument so the doctor can run its history-assembly checks from a local
template file, closing gap 2 for every local-weights stack, not just MLX.
Doing that check by hand on this lane found a real write-field divergence the
skip had left invisible (trap 20's mlx_lm section), which is the argument for
building it. Until then, use
[checks/preflight_template.py](../checks/preflight_template.py), which
already accepts `--template-file`.

## What it cannot see

The doctor is request-shaped where the stack gives it nothing better: on
servers with no template endpoint and no readable template it cannot
inspect the assembled prompt (it says so and points at
[checks/preflight_template.py](../checks/preflight_template.py), which
accepts `--template-file`). It probes one model per run; pass `--model`
to pick one on multi-model servers. It sends a still image only: audio and
video paths, their decoders, error classes and token costs are declared
uncovered in every run rather than left implied.

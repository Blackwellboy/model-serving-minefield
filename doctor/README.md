# minefield-doctor

## Offline research-integrity companions

Endpoint doctor remains a **thinking-stack preflight** (below). Separate
offline tools validate research evidence without probing a lane:

| Command | Purpose |
|---------|---------|
| `python3 -m minefield evidence-preflight --packet FILE` | Evidence Packet integrity (PASS/HOLD/FAIL/UNKNOWN) |
| `python3 -m minefield blind-review --packet FILE` | Strip proposer verdict/confidence for falsification |
| `python3 -m minefield upstream-triage` | Map changed paths to risk surfaces (not new traps) |
| `python3 -m minefield promotion-receipt --receipt FILE` | Validate a promotion provenance receipt |

See [`playbooks/agentic-research-integrity.md`](../playbooks/agentic-research-integrity.md).
These tools report observation counts and never treat HTTP health alone as
model capability proof.

## What this tool actually is: a thinking-stack preflight

The name says doctor, and the name is bigger than the tool. Read it as a
**thinking-stack preflight**, not a minefield doctor.

Its 19 checks cluster almost entirely on one region of the registry: reasoning
field names, chat templates and history assembly, thinking control kwargs,
tool parsing, and token ceilings. That is not an accident of what got built
first, it is what a read-only, request-shaped probe can reach in under a
minute. The regions it says **nothing** about include quantisation kernel
paths, container toolchains and driver mismatches, memory allocation and KV
sizing, MoE routing, every eval-harness confound, and long-context behaviour.
Those are most of this registry, and they are where several of the
[Core 12](../CORE.md) live.

So: a PROBLEM from this tool is a real defect worth acting on. A run with no
problems means the handful of trap ids in its `clean` count were ruled out on
your lane, and nothing more. The coverage block below is deliberately
unflattering and it prints on every run; do not let a clean summary line talk
you out of reading it.

Findings are ordered **Core first** within each verdict bucket, so the checks
most likely to matter are the first lines you read.

## Running it

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

A third audit pass found four more, all under the same contract, plus two the
same sweep turned up. These are now not clean either:

- **A located quantisation manifest.** Finding `quantization_config` in
  `config.json`, or the scheme in `hf_quant_config.json`, establishes what the
  checkpoint is **labelled**. Trap 10's failure mode is the engine taking a
  different kernel path from the one the label implies, and no file on the hub
  can rule that out. Both branches are now INCONCLUSIVE and name the runtime
  tells that would settle it: the engine's backend-selection log, decode
  throughput against an f16 baseline, or utilisation against power draw.
- **Content present on a ceiling probe that never hit the cap.** One request
  at `max_tokens=512` that finished early does not exercise a defect which
  only appears when the budget runs out. That is `CEILING_NOT_REACHED`,
  INCONCLUSIVE. CLEAN for trap 12 now requires `finish=length` **with**
  content, which is the only single-probe observation that rules the failure
  mode out.
- **An explicit-off arm that still fires.** The toggle map printed
  `off fired=True` and filed the whole thing under CHECKED AND CLEAN anyway.
  An off switch that does not turn thinking off is now
  `EXPLICIT_OFF_STILL_FIRES`, a PROBLEM. Trap 03 reaches CLEAN only when
  explicit-on fires, explicit-off does not, and the absent arm is reported as
  on-like, off-like or distinct without any claim that omitting the kwarg is
  safe.
- **`reasoning_effort` appearing in the template text.** A substring hit means
  the name is **referenced**, not that it is read: it can sit in a comment, in
  a branch that never runs, or in a `set` that is never used afterwards. This
  file's own fixture template is that last shape. Now
  `KWARG_REFERENCED_BY_TEMPLATE`, INCONCLUSIVE, pointing at the render diff
  that would settle it.
- **A render with no empty think shells no longer clears trap 04.** The
  absence of `<think></think>` pairs is trap 25's failure mode directly, and
  it is now scoped to 25. A lane that drops prior reasoning and emits no
  wrapper at all produces exactly this render. Trap 04 takes its verdict from
  the write-field probe, which can settle it.
- **A CLEAN whose assertion log contradicted it.** Trap 26 recorded
  "no raw `<tool_call>` markup" with `markup_seen: True` beside it, held. Raw
  markup alongside parsed calls is now `TOOL_MARKUP_PARTIALLY_PARSED`, a
  PROBLEM, and the assertion records what was actually seen.

`EMPTY_CONTENT_AT_CAP` also stopped over-tagging. It reported traps 12, 22 and
16 from one probe; trap 22 needs a cross-size comparison and trap 16 is about
scoring `finish_reason`, so the finding now tags **12** alone, with the
degeneration heuristic demoted to a separate annotation that says plainly it
is two numbers over one sample.

### The rule, enforced mechanically

Three hardening passes each converted the false CLEANs they happened to look
at, and each missed others. So the guard is no longer "review the `ok()`
calls". `doctor/tests/test_doctor_verdicts.py` carries `CLEAN_CONTRACT`: every
CLEAN this tool is permitted to emit, each with the failure mode it rules
**out**. A sweep across every fixture scenario collects the CLEANs the tool
actually produces and fails the build in both directions, on a verdict missing
from the table and on a table entry no scenario can produce. A new clean
verdict cannot be added without writing down what it rules out.

## Coverage, stated plainly

The doctor implements checks for **19 of the registry's 135 numbered entries**
(01, 02, 03, 04, 07, 10, 12, 16, 17, 19, 20, 21, 22, 23, 25, 26, 29, 77, 78).
Every run ends with a coverage line:

```
implemented 19/135 | executed on this stack N | clean N | problems N | inconclusive N | not implemented 116
```

`executed on this stack` counts trap ids that received a CLEAN or PROBLEM
verdict on that run, which on a real lane is well under 17. Even 17 overstates
depth, and the coverage block says so every time:

- **25** shares the trap-04 history-render heuristic. It is not a separate
  probe: one render inspection decides both.
- **16** is an annotation on the trap-12 ceiling finding. It has no
  independent probe.
- **10** and **22** can **never reach CLEAN**, and the coverage block says so
  on every run. The trap-10 check reads the checkpoint's quantisation
  manifest, which establishes the label rather than the kernel path the engine
  took. Trap 22 is a claim about a distribution across sizes and budgets, and
  this tool sends one request at one budget, so it is linked from the ceiling
  check purely so you can find the entry, and is never given a verdict by it.
- **10, 17, 21** need `--hf-repo`. Without it they cannot run at all.
- **04, 20, 25** need a render path. On a stack that exposes none they cannot
  run at all.
- **77** is the newest and the cheapest: one baseline request and one request
  carrying an invented top-level field. It runs first, because it decides
  whether a 200 from this lane carries any information at all about whether a
  parameter was read, and every check after it sends parameters. Its CLEAN is
  paired and narrow: the invented field must be rejected **while the identical
  request without it returns 200**, which is what stops a wrong model name or
  an expired key reading as a strict server. It rules out "your typo is
  silently accepted"; it does **not** rule out a known-but-unimplemented field
  being accepted and ignored, which stays with 03 and 29.
- The remaining **116** numbered traps have no check in this tool.

The multimodal checks (`mm-surface`, `mm-usage`, `mm-order`, `mm-errors`,
`mm-audio-video`) are **advisory**: they can report a PROBLEM or a CLEAN of
their own, and there is no trap file and no README row behind any of them.
Every run labels them as such on the finding line and lists them in the
coverage block, and they are counted nowhere in the trap-id arithmetic above.

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
  **17 chat completions**, each capped at 512 output tokens or less, all at
  temperature 0. 17 is the reachable budget when every applicable probe runs;
  a lane that skips probes issues fewer, and two contributor-measured SGLang
  runs issued 14. Size any rate limit on 17, not on an observed count. It also calls render or tokenise routes
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
| Ceiling: empty content at cap, empty content *without* a cap hit, content at a real cap hit | 12, 16 |
| Budget floor across sizes: **not checked**, declared uncovered every run | 22 |
| Streaming: answer deltas in `content` vs reasoning channels, thinking off | 23 |
| `generation_config.json` exists at the compared revision; server defaults vs shipped config, on shared keys only | 21, 17 |
| Quantisation **label** in `config.json`, then `hf_quant_config.json`. Never the kernel path, so never clean | 10 |
| Multimodal surface, usage attribution, content-part ordering, media error classification | advisory, not in the registry |

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
`content` key was entirely absent, without crashing (trap 12; that finding
was tagged 12/16/22 at the time and is now tagged 12 alone). Its clean
verdicts (traps 02/19/23) matched independent probes.

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

This whole section is a **2026-07-27 field report against the doctor as it
stood that day**, and several verdicts in it have since been re-classified.
Read it as a portability record, not as a current verdict set for that lane.
In particular the trap 03/29 toggle result would now be re-read against the
explicit-off branch, and any trap-12 clean would need a real cap hit. Nobody
should quote a verdict from this paragraph without re-running the doctor at
the current tip.

**Planned (tracked enhancement, not yet implemented):** a `--template-file`
argument so the doctor can run its history-assembly checks from a local
template file, closing gap 2 for every local-weights stack, not just MLX.
Doing that check by hand on this lane found a real write-field divergence the
skip had left invisible (trap 20's mlx_lm section), which is the argument for
building it. Until then, use
[checks/preflight_template.py](../checks/preflight_template.py), which
already accepts `--template-file`.

## Portability notes: SGLang 0.5.16 on DGX Spark

Two contributor-measured runs each issued **14 chat requests** against pinned
NVFP4 checkpoints on a GB10 lane.

**14 is what those two runs observed, not a maximum.** How many requests a run
issues depends on which probes apply to the lane: a strict multimodal lane on
which the primary off-control fires reaches **up to 17**, counted from the call
sites as 2 request-validation, 4 reasoning controls (on, off, absent, plus one
alternate off spelling), 1 streaming, 3 kwarg-deadness, 2 multimodal, 2 tool,
2 tool-choice and 1 ceiling. Treat 14 as the observed count on those two lanes
and 17 as the reachable budget, and do not size a rate limit or a lane window
on the observed number. The Nemotron run executed 11 numbered checks and
the Laguna run executed 8. The saved assertions matched independent request
controls: trap 77's invented top-level field was accepted on both lanes, and
Laguna reproduced the trap 12 cap-hit and trap 02 orphan-close response shapes.
Inconclusive quantisation and toggle results stayed inconclusive. Full
conditions and the Q7/Q8 disposition are in the
[SGLang field note](../mining/2026-07-28-sglang-nvfp4-and-doctor-dgx-spark.md).

The probes were portable; stack detection was not. SGLang exposes neither
`/props` nor `/version`, so both reports originally printed the anonymous
OpenAI-compatible label even though `/v1/models` returned
`owned_by: "sglang"`. The detector now reads that model-row field before it
falls through to the anonymous bucket. A fixture carrying the real response
shape failed before this change and passes after it. The same field run
established that SGLang reads
`chat_template_kwargs.enable_thinking`, so SGLang is also in the doctor's set
of stacks with a known off-control spelling.

*Status of this field report: contributor-measured, conditions as reported, by
[@newageinvestments25-byte](https://github.com/newageinvestments25-byte).*

## What it cannot see

The doctor is request-shaped where the stack gives it nothing better: on
servers with no template endpoint and no readable template it cannot
inspect the assembled prompt (it says so and points at
[checks/preflight_template.py](../checks/preflight_template.py), which
accepts `--template-file`). It probes one model per run; pass `--model`
to pick one on multi-model servers. It sends a still image only: audio and
video paths, their decoders, error classes and token costs are declared
uncovered in every run rather than left implied.

## Readiness is a completed generation, not an endpoint answering

Recorded here because it has now cost two separate things, and because this
tool is where an operator looks for how to check a lane.

**`/v1/models` answering is NOT readiness.** On most serving stacks that route
responds as soon as the HTTP server binds, which is well before weights are
resident and long before the lane can generate. A poll that gates on it reports
one of two wrong answers depending on timing: a connection refusal while the
lane is merely still starting, or a 200 while nothing has loaded. On a large
checkpoint the gap between binding and being able to generate is minutes.

It bit the fleet's own lane-release helper, whose restore probe hit that route
immediately after container start, and it bit a session's first wait loop on
2026-07-28. Both read a bound socket as a ready model.

**Readiness is a completed generation.** Send one small request with a real
token budget and require content back before you call the lane up. A probe that
has not produced a token has not established that the lane can produce one, and
this doctor's own rule applies to it: a result reaches clean only when the
observation rules the failure mode out, rather than merely failing to observe
it.


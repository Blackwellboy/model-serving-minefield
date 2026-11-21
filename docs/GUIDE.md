# Model Serving Minefield: the full guide

The [README](../README.md) is the short version. This page keeps the detail
that used to live there: the doctor, every way in, the pre-serve checklist,
categories, contributing, contributors, recent additions, methodology and
scope. The full symptom table is [TRAPS.md](../TRAPS.md).

## Evidence staging privacy

This public repository contains the canonical published registry and public-safe governance. Raw candidate research, unpublished source harvests, unresolved private evidence, and editorial drafts are staged privately and are **not** stored in this repository. Promotion into this repo is deliberate and sanitized.


## Preview Doctor work before connecting a live model

`minefield doctor-plan --mode lite --max-requests 5 --text` lists the
bounded checks a future live pass would select, without contacting your
endpoint, Hugging Face or GPU. No planned check is reported as executed.
See [the CLI reference](../docs/CLI_REFERENCE.md#plan-live-doctor-checks-without-contacting-a-server).

## Diagnose everything you have at once

When you have a symptom plus files and/or a live endpoint, use the unified
front door instead of running the matcher, scanner and Doctor separately:

```bash
minefield diagnose "tp=2 dies after twenty minutes" \
  --files docker-compose.yml start.sh ./logs/ \
  --base-url http://HOST:8000/v1
```

Minefield considers all **175 canonical traps** for routing, scans the supplied
files, auto-detects the endpoint stack/model when available, and spends its
bounded live-probe budget on checks related to the traps already surfaced by
the symptom/files before falling back to generic lite probes. The output keeps
evidence types separate: text and file hits are leads; live Doctor findings are
reported as bounded endpoint observations.

## Diagnose with an AI agent

**Agent can access GitHub:** give it
[`AGENT_START_HERE.md`](../AGENT_START_HERE.md) plus your redacted logs or
configuration:

> Read the Model Serving Minefield agent start file, diagnose this serving
> problem, separate confirmed from possible matches, and give confirmation
> checks before suggesting changes.

**Agent cannot access GitHub:** download and upload
[`dist/MINEFIELD_AGENT_BUNDLE.md`](../dist/MINEFIELD_AGENT_BUNDLE.md).

**Preparing live model qualification:** follow the staged
[live-model qualification protocol](../docs/LIVE_MODEL_QUALIFICATION.md)
before measuring a 5090, Spark or multi-node lane.

**You have a live endpoint:** install the package and run the bounded,
read-only doctor:

```bash
pipx install model-serving-minefield
minefield quick --base-url http://HOST:PORT/v1 --json doctor.json
```

**Hermes user:** install the [`hermes-minefield`](https://github.com/Blackwellboy/hermes-minefield)
plugin and type `/minefield` for the menu; the skill and MCP server also work.
See [Hermes setup](../docs/HERMES_SETUP.md).

**MCP user:** run `minefield-mcp` over stdio. It exposes search,
report-interpretation, reproduction-plan, explicit-file inspection and a
`list_menu` tool (the same numbered menu as the CLI);
it cannot restart or modify a server. See [MCP setup](../docs/MCP_SETUP.md).

The second badge is the one worth explaining. `surfaces` runs hourly and asks
whether the public pages still agree with this tree, including the Pages site
in another repo. It does not gate a push, because the site rebuilds after the
push that moves this tree and cannot have caught up at that moment. It goes red
when a published figure has actually drifted. It is here rather than only in the
Actions tab because the last two guards in this project were built and then sat
unwired, and a count nobody looks at is not a check.

## Start here

Four doors, and which one you want depends on why you are here. All 175
entries are too many to read; none of these asks you to.

- **"What am I doing?"** The **[playbooks](../playbooks/)** are ordered checklists
  for the seven playbook jobs people actually arrive with:
  [before you publish an A/B](../playbooks/before-you-publish-an-ab.md),
  [thinking died when I made it multi-turn](../playbooks/thinking-died-multi-turn.md),
  [porting a harness to a new server](../playbooks/porting-a-harness.md),
  [long context looks broken](../playbooks/long-context-looks-broken.md),
  [reading a soak](../playbooks/reading-a-soak.md),
  [agentic research integrity](../playbooks/agentic-research-integrity.md), and
  [minefield repro loop](../playbooks/minefield-repro-loop.md). Symptom
  playbooks sequence existing entries; research-integrity playbooks keep
  target bugs distinct from research-stack bugs.
- **"What am I running?"** The **[per-stack pages](../stacks/)** give you the five
  entries most likely to bite on
  [vLLM](../stacks/vllm.md), [llama.cpp and GGUF](../stacks/llama-cpp.md),
  [Ollama](../stacks/ollama.md), [sglang](../stacks/sglang.md) or
  [mlx_lm](../stacks/mlx.md), plus the three checks
  to run before anything else.
  **Every stack has a page, including the ones we have never run**:
  [HF transformers](../stacks/hf-transformers.md),
  [TensorRT-LLM](../stacks/tensorrt-llm.md),
  [text-generation-inference](../stacks/text-generation-inference.md),
  [TabbyAPI and ExLlama](../stacks/tabbyapi.md) (an ExLlamaV3 evaluation
  lane only, no TabbyAPI server),
  [LM Studio](../stacks/lm-studio.md) and
  [text-generation-webui](../stacks/text-generation-webui.md). Those open by
  saying what they do **not** have, then name which mechanism classes most
  likely apply there and why, with the check you would run. "We have not tested
  this, here is what to look for" is more useful than an absent page, which
  reads as nothing to see. The
  **[per-model and per-stack index](../models/README.md)** is the full map,
  including layers that are not serving stacks. Absence from either means
  nobody has reported on that model here, not that it is safe.
- **"What am I seeing?"** The **[symptom table](../TRAPS.md)** is
  in [TRAPS.md](../TRAPS.md): all 175 entries, one row each. It is the
  answer to a weird number you are holding right now. That is the premise of
  this registry and it has not moved; it is placed after these doors only
  because most visitors arrive before the symptom rather than during it.
- **"What should I read first?"** The **[Core 12](../CORE.md)**, chosen on
  evidence of what has cost people evenings rather than on which entries have
  the best data. Everything else is Extended, which means specific rather than
  lesser.

In a hurry and holding an endpoint? [Run the doctor](#run-the-doctor) against
it. It is a **thinking-stack preflight, not a minefield doctor**: it has checks
for **70 of these 175 entries**, weighted toward reasoning fields, templates,
tool parsing and multimodal handling, and a clean run from it says nothing about
the other 105. It runs
in under a minute and prints its own coverage line at the end of every run so
you can see exactly how much of the registry it touched, how much it could not
check on your stack, and how much it never implements.

**Things that did not work out** are collected in private evidence archive *(private evidence archived)*: the
candidates we tested that **did not reproduce**, the ones that are **blocked or
not testable** on the lanes available, and the ones that are **specification
only, not run**. A negative is information, and it is often the fastest way to
stop chasing a ghost somebody else already chased.

**Reports we have not been able to run** are published too, in
[upstream/](../upstream/), and they are kept in their own directory rather than
mixed in so the difference is obvious at a glance. Credited reports from
other people's issue trackers, on stacks and hardware we do not have, each
carrying the primary source, who reported it, whether a maintainer engaged, the
issue state, a plain statement that **nobody here has reproduced it**, and what
you would run to settle it. Two of them were reproduced by a maintainer and
then closed by a staleness bot, which is not the same as fixed. They never
appear in [Core](../CORE.md), never count toward doctor coverage, and never count
toward the registry total; a checker asserts all three on every run.

**Open trap-adjudication questions** are public in
[registry/OPEN_TRAP_ISSUES.md](../registry/OPEN_TRAP_ISSUES.md). Every currently
open GitHub issue whose title begins `[trap]` must be represented there with
CONFIRM and REFUTE criteria fixed **before** adjudication; CI compares the queue
against live issue state. Broader raw candidate research, blocked reproductions
and negative evidence remain in the private evidence archive rather than being
published as if settled.

## Run the doctor

**Name it honestly: this is a thinking-stack preflight, not a minefield
doctor.** Its checks cluster on reasoning fields, chat templates, thinking
control, tool parsing and token ceilings, because that is where its
request-shaped probes can reach. It has nothing to say about quantisation
kernel paths, container toolchains, memory allocation, eval-harness confounds
or long-context behaviour, which is most of this registry. A clean run is a
statement about a handful of trap ids, never a bill of health.

With that said, one stdlib-only file, no install, that diagnoses your endpoint
against 70 of this registry's 175 entries in under a minute:

```bash
curl -sO https://raw.githubusercontent.com/Blackwellboy/model-serving-minefield/main/doctor/minefield_doctor.py
python3 minefield_doctor.py --base-url http://localhost:8000/v1
```

Read-only and bounded: GET probes plus at most 12 small temperature-0
completions, nothing sent anywhere but your endpoint. Add
`--hf-repo org/name` for the checkpoint-config checks, and
`--hf-revision <tag or commit>` if you serve a pinned revision rather than
whatever `main` holds today.

Output is PROBLEMS / CHECKED AND CLEAN / INCONCLUSIVE / COULD NOT CHECK,
followed by a coverage line. A result only reaches CHECKED AND CLEAN when
the observation rules the trap out; where acceptance, silence, or a missing
template would explain the same result, it is reported as INCONCLUSIVE or
COULD NOT CHECK instead. Every finding links its trap, and `--report`
emits a paste-ready block for the
["I hit a trap" form](../../../issues/new?template=report-a-trap.yml). Full
safety story, check list and coverage caveats in
[doctor/README.md](../doctor/README.md).

## Before you serve a new model

The one-line checklist, each line backed by an entry. Lines 2, 3, 4, 5 and
the first two thirds of line 8 have a check in [the doctor](../doctor/); lines
1, 6, 7 and the echo-and-logprobs part of line 8 do not, and are yours to
run. Runnable pieces also live in [checks/](../checks/).

1. Image toolchain matches the host driver ([08](../traps/runtime/08-image-toolchain-newer-than-driver.md)); record the image digest ([09](../traps/runtime/09-image-choice-changes-outcome.md)).
2. Read `config.json`'s quant schemes, not the repo name ([10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md)).
3. One tool-defined request returns a structured `tool_calls` array ([19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md)).
4. Both reasoning field names read, positive control fires ([01](../traps/reasoning/01-reasoning-field-two-names.md)), thinking kwarg sent explicitly ([03](../traps/reasoning/03-enable-thinking-default-drift.md)).
5. Assembled prompt inspected at turn 3 with a marked reasoning string ([04](../traps/template/04-history-reasoning-stripping.md); [checks/preflight_template.py](../checks/preflight_template.py) automates it).
6. Attention implementation confirmed on, benchmarked at real depth ([18](../traps/runtime/18-flash-attention-off-halves-deep-decode.md)).
7. KV sized in bytes on unified memory ([13](../traps/memory/13-utilization-fraction-on-unified-memory.md)); speculative K swept, not searched ([11](../traps/runtime/11-speculative-depth-peak-and-collapse.md)).
8. Scores bucketed on extractable output, ceilings of at least 8192, echo+logprobs probed before multiple-choice evals ([16](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md), [12](../traps/evaluation/12-empty-content-at-token-ceiling.md), [15](../traps/evaluation/15-no-echo-logprobs-wedges-lm-eval.md)).

## Categories

| Directory | Covers |
|---|---|
| [traps/template/](../traps/template/) | Chat templates, history assembly, prompt rendering |
| [traps/tools/](../traps/tools/) | Tool calling, parsers, structured output |
| [traps/reasoning/](../traps/reasoning/) | Reasoning fields, thinking kwargs and control |
| [traps/quantization/](../traps/quantization/) | Quant formats, precision, kernel paths |
| [traps/routing/](../traps/routing/) | MoE expert routing and activation config (top-k, gate weighting) |
| [traps/runtime/](../traps/runtime/) | CUDA and toolchains, container images, attention and speculative config |
| [traps/memory/](../traps/memory/) | KV cache, memory allocation, context windows |
| [traps/evaluation/](../traps/evaluation/) | Harness traps, scoring, budgets, confounds |
| [traps/versioning/](../traps/versioning/) | Revisions, builds, re-uploads, distribution |

Old flat paths (`traps/NN-*.md`) remain as redirect stubs so existing links
keep resolving.

## How to contribute

Two doors. Take the easy one; it counts just as much.

- **Easy door: you hit a trap, tell us in plain words.** Open an
  ["I hit a trap" issue](../../../issues/new?template=report-a-trap.yml). Four
  plain questions, no formatting, no writeup. A maintainer verifies what can
  be verified, writes the entry, credits you by name, and links your issue.
  Most entries should start this way.
- **Research-stack door:** harness, scorer, agent-evidence, or measurement
  process failed (keep this distinct from a model bug). Use
  [research-stack failure](../../../issues/new?template=research-stack-failure.yml)
  and the
  [agentic research integrity](../playbooks/agentic-research-integrity.md)
  playbook. No trap number is promised.
- **Full door: write the entry yourself.** One file under the right
  `traps/<category>/`, format and evidence bar in
  [CONTRIBUTING.md](../CONTRIBUTING.md), PR template walks the checklist.

Minefield can validate the **research system** as well as the served model:
a TARGET BUG and a RESEARCH-STACK BUG must stay distinct. Evidence Packet
preflight and related offline tools are documented in the playbook above; they
help detect known evidence-integrity failure classes, not certify bounty
findings as valid.

Not sure whether what you hit is a trap or your own mistake? Open the issue
anyway. "I could not tell whether this was me or the stack" is exactly the
state these entries exist to resolve, and triage is cheap.

How reports become entries, and how statuses are assigned, is documented in
[MAINTAINING.md](../MAINTAINING.md). Candidates that were tested and did not
(or could not) promote are recorded in private evidence archive *(private evidence archived)*; a negative is
information too.

## Contributors

Findings in this registry come from **@quantumleap68**,
**TheTom** ([offlabel](https://github.com/TheTom/offlabel)),
**@Defilan**, **@apollo-mg**,
**@mrpmorris** ([sparkrun-recipes](https://github.com/mrpmorris/sparkrun-recipes)),
**eugr** ([spark-vllm-docker](https://github.com/eugr/spark-vllm-docker)),
**@Hikari_07_jp** ([qwen36-a6b](https://github.com/hikarioyama/qwen36-a6b)),
**@drowzeys** ([Keys](https://github.com/drowzeys)),
**@newageinvestments25-byte**, **Exile**,
and **Blackwellboy** ([laguna-s21-lab](https://github.com/Blackwellboy/laguna-s21-lab)).
Per-finding credit is in [HALL_OF_FAME.md](../HALL_OF_FAME.md), and every entry
names its finder at the top. Contributors are always named unless they ask
otherwise.

## Recently added

- 2026-10-15: **traps [165](../traps/reasoning/165-thinking-off-for-agent-speed-costs-reasoning.md) and [166](../traps/reasoning/166-per-call-thinking-switch-splits-prefix-cache.md)** - thinking off as an agent speed fix keeps tool steps (14/15) and loses in-agent reasoning (8/24 vs 24/24), while thinking every step made a real stretch 258 s against 53 s for thinking only after the user speaks (**measured here, raw not published**); each thinking setting or effort level is its own prefix-cache entry, cold on first use even at identical `prompt_tokens` (**reproduced here**). Registry 164→166.
- 2026-10-15: **trap [164](../traps/reasoning/164-thinking-budget-cut-hides-the-answer.md)** - a thinking-token budget that actually cuts the reasoning hides the answer and runs to `max_tokens` (0/6 answers capped vs 3/3 uncapped on a DeepSeek-V4.1 vLLM lane; **reproduced here**). Registry 163→164.
- 2026-09-02: **traps [136](../traps/evaluation/136-pipeline-reports-consumer-status-not-producer-failure.md) and [137](../traps/evaluation/137-kernel-selector-return-is-not-process-exit-status.md)** - preserve the producer's pipeline status and distinguish native-extension dispatch selectors from process exit codes (**contributor-measured, conditions as reported**); the agentic research playbook gains implementation-path proof gates. Registry 135→137.
- 2026-08-25: **trap [135](../traps/evaluation/135-concurrent-http-clients-are-not-concurrent-model-execution.md) + Trap [134](../traps/evaluation/134-link-up-is-not-path-proof-for-the-interface-under-test.md) controlled TRANSPORT addendum** - concurrent HTTP clients are not concurrent model execution (**measured here, raw not published**); Trap 134 gains the positive holds+path-proof TRANSPORT corroboration; offline `concurrency_execution_proof_preflight`. Registry 134→135. Mining note *(private evidence archived)*.
- 2026-07-28: **first published SGLang evidence surfaces**, contributor-measured by [@newageinvestments25-byte](https://github.com/newageinvestments25-byte) on a DGX Spark. A pinned Nemotron NVFP4 control generated first; Laguna S 2.1 loaded its compressed-tensors NVFP4 MoE path and generated a correct first token, refuting Q7 under its pre-registered generation criterion without claiming healthy long-form output. Two 14-request doctor runs confirmed Q8 portability and reproduced SGLang instances inside traps [02](../traps/template/02-orphaned-think-close-tag.md), [12](../traps/evaluation/12-empty-content-at-token-ceiling.md) and [77](../traps/reasoning/77-only-one-request-field-is-validated.md). The same run found and regression-tested a doctor fix: SGLang identifies itself in `/v1/models`, not `/version`. Conditions and bounded disposition *(private evidence archived)*.
- 2026-07-28: **traps [91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md) through [97](../traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md): the determinism axis, and the registry's first cross-architecture and co-tenancy coverage**, on the same llama.cpp lane as 82 to 88. The one to read is [91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md), because its failure mode is a **false negative**: temperature-0 divergence under concurrency needs a prompt above roughly 220 tokens, and the natural minimal reproduction is shorter than that, so the check passes and the lane is not deterministic. [93](../traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md) is the one that corrects widely repeated advice: on a template that relocates the system block, a clock at the head of the system prompt is inert (136 cached tokens against 135), and moving it into the first user message, which is the usual remedy, is the single change that takes reuse from 77% to 0.6%. [94](../traps/runtime/94-temp0-reproducibility-is-architecture-dependent.md) is a regime and not a ranking: `sm_86` and `sm_120` both diverge at 220 tokens, and only `sm_120` still diverges at 444. [95](../traps/runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md) is a **negative** that removes a standing caveat, and it states the case it does not cover. [92](../traps/runtime/92-prompt-cache-is-a-second-divergence-source.md) is a self-caught error: prompt-cache state survived across separate invocations against one process and inverted one of our own results before we found it.
- 2026-07-28: **traps [82](../traps/template/82-system-prompt-relocates-to-last-user-turn.md) through [88](../traps/runtime/88-cache-prompt-false-does-isolate-here.md): a fourth serving stack**, llama.cpp with `--jinja` against a Mistral-family Q8_0 GGUF of unstated provenance supplied by **Exile**. The checkpoint is deliberately not characterised and nothing here generalises to any named model. Headline: an agent loop of user, tool call, tool result, user is **unrenderable** and the 400 blames the template rather than your message list; and the template carries a hard-coded default system prompt injected whenever you omit one, so a no-system-prompt control arm **is not a control**. Also a negative worth as much as the positives: [88](../traps/runtime/88-cache-prompt-false-does-isolate-here.md) finds `cache_prompt: false` DOES isolate on this build, a third data point that does not reproduce two prior stacks, and it lands with its build qualifier attached.
- 2026-07-28: traps [89](../traps/evaluation/89-hardlink-shard-pollution-invalidates-a-ladder.md) and [90](../traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md), from [@drowzeys](https://github.com/drowzeys) (Keys), shared from his public notes. An in-place weight edit that mutates the stock copy through a shared inode, so every comparison against it is quietly wrong; and a kernel library shipping cubins for one architecture only, behind six errors that each look like a fixable config bug. Two further findings of his landed inside traps [62](../traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md) and [79](../traps/memory/79-out-of-range-context-request-accepted.md) rather than taking numbers.
- 2026-07-28: trap [33](../traps/routing/33-moe-inference-topk-expansion-tax.md) **promoted to reported by others + reproduced here.** The top-k expansion tax was landed from a research log whose every number is bf16 under HF transformers; it reproduces on our own **NVFP4** build, where under this registry's own rule a different quantisation is a different unit under test and the question was genuinely open. Monotone across four values of k, in two scoring protocols, on two independent passes each: k=8 to k=32 is **-4.50 points** at n=600 paired, discordant 37 against 10, exact McNemar **p = 9.8e-05**, with the independent replicate at -4.00 and p = 0.000936. Method, both protocols and the runnable scripts *(private evidence archived)*. **This is the second time a first-party run has confirmed an external contributor's finding here**, and as with the first, [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b) keeps the **Found by** line.
- 2026-07-28: **traps [75](../traps/versioning/75-release-asset-renamed-pinned-url-404.md) through [81](../traps/memory/81-stopped-container-has-not-released-memory.md): first Ollama coverage**, which [CONTRIBUTING](../CONTRIBUTING.md#where-coverage-is-thin) had listed as a stack with no entries at all. The one with the highest operator cost is [77](../traps/reasoning/77-only-one-request-field-is-validated.md): exactly one request field is validated, so a harness ported from another server sends `enable_thinking: false`, gets HTTP 200, and measures its entire thinking-off arm on a thinking lane. Also [78](../traps/tools/78-tool-choice-accepted-and-ignored.md), where `tool_choice` is inert in both directions and therefore **fails open** on the standard way an agent framework gates a turn. Two further findings landed inside existing entries: a third reasoning field name split by route ([01](../traps/reasoning/01-reasoning-field-two-names.md)) and the injection mirror of the in-text toggle ([66](../traps/template/66-in-text-thinking-toggle-mutates-user-text.md#the-mirror-case-injection-on-ollama)). The same pass settled R2-39 on the stack it was scoped to, and established that SGLang is not infeasible *(private evidence archived)* on this hardware class.
- 2026-07-28: **traps [63](../traps/reasoning/63-reasoning-round-trip-one-correct-shape.md) through [74](../traps/evaluation/74-non-speech-audio-fabricated-captions.md): the NVIDIA Nemotron 3 family**, three checkpoints including this registry's first multimodal lane, characterised across three sessions and merged. Headline: the reasoning round trip has exactly **one correct shape out of four**, because the preservation gate is named `truncate_history_thinking` and **true means discard**, the opposite polarity to the name this registry already documents, so a pipeline standardised on the other one silently no-ops. Also: a template that scans user text for `/think` and `/no_think`, obeys them over the documented keyword, and deletes them from the prompt, so any path or URL containing those characters is silently rewritten. Eight more findings landed as **additions to existing entries** rather than new numbers, including a measured empty-content floor and the proof that no single floor is safe to copy.
- 2026-07-28: **traps [56](../traps/template/56-checkpoint-ships-no-chat-template.md) through [62](../traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md): first coverage of a DeepSeek-V4-Flash serving path**, measured at request level against a live two-node lane. The checkpoint ships no chat template at all, only Python; the thinking kwarg is evaluated for truthiness so the string `"false"` turns thinking on; `reasoning_effort` is an undocumented thinking switch that also injects a hidden preamble, and only at the top level; prior-turn reasoning is discarded by every field name and the model confabulates it back on request; a cold prefill and a prefix-cache hit answer the same prompt differently; and the advertised million-token window rests on a 64K trained base with nothing anywhere reporting the difference. Full serving path and the traps in one place on the [model page](../models/deepseek-v4-flash.md). A pre-registered experiment that would separate the cache result's two candidate mechanisms is written but NOT RUN *(private evidence archived)*, because it needs a serve change and the lane is production.
- 2026-07-28: **traps [43](../traps/template/43-tool-args-string-not-mapping.md) through [55](../traps/evaluation/55-supported-context-is-not-trained-context.md): the registry's first large external contribution**, thirteen entries from [@TheTom](https://github.com/TheTom), who maintains the offlabel operator guide. All land at **contributor-measured, conditions as reported**: he measured every one on his own hardware and stated the conditions, and we have not reproduced them here. Headline classes: a chat template that renders replayed tool arguments empty when they arrive as a JSON string, an FP4 dequant that reads its scales in the wrong layout so the damage is distributed rather than obvious, KV-quant pairs with no compiled flash-attention kernel, a binary that predates its own arch-native kernel, prefix caching silently auto-disabled on hybrid architectures, and a run of measurement traps that each produced a clean reproducible number that was not real. **Numbering is provisional**; see [MAINTAINING.md](../MAINTAINING.md#numbering-in-this-merge).
- 2026-07-28: trap [42](../traps/evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md): a single-turn eval harness scores `finish_reason=tool_calls` as a wrong answer, so attaching an agent prompt and tool schemas costs measured score without costing capability. Found and measured at n=492 by [@apollo-mg](https://github.com/TheTom/offlabel/pull/10#issuecomment-5093534067) with raw published: pooled pass@1 fell 18.9 points while wrong answers moved by one and accuracy conditional on attempting held at 91.71%. Carries the two detection fingerprints (conditional against pooled; bucket by exit path, not by score) and a pre-registered open question, with both predictions on record, about whether the termination benefit survives tool output being fed back.
- 2026-07-28: nine traps ([33](../traps/routing/33-moe-inference-topk-expansion-tax.md) through [41](../traps/runtime/41-static-batching-buys-power-not-throughput.md)) mined from [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)'s public research log on expanding a pretrained MoE's inference top-k, offered by him for this purpose. Headline: raising a MoE's active-expert count from 8 to 32 costs accuracy before any training, silently, because renormalization dilutes the original top-8 rather than adding to it. New [routing/](../traps/routing/) category for MoE activation config. The rest are measurement traps that made real numbers wrong: a baseline you degraded yourself, identical weights not scoring identically, token caps binding unequally per arm, all-arms-zero as a harness verdict, the opening think tag the template owns, `device_map="auto"` spilling silently, contamination screens firing on boilerplate, and static batching buying power instead of throughput.
- 2026-07-27: trap [32](../traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md): mlx_lm's server `--max-tokens` flag is a per-request default, not a cap; a client can quietly run past it. Same pass landed MLX-scoped sections in six existing entries (mlx_lm now has real coverage in the [per-stack index](../models/README.md)) and the new private evidence archive *(private evidence archived)* verification-notes area for candidates that did not or could not promote.
- 2026-07-27: trap [31](../traps/evaluation/31-leftover-oracle-reranker.md): a leftover oracle re-ranker (a debugging script that boosts candidates by expected id or looks them up by the answer's file name stem) turns a failing retrieval eval into a passing one, and the inflated number outlives the script; with the two detection fingerprints (top-1 equals top-3 exactly; saturation at exactly 1.0) and a copyable no-oracle negative control.
- 2026-07-27: trap [30](../traps/template/30-default-system-message-silently-replaced.md): the template's default system message vanishes the moment you send your own, so every with-system-prompt condition also toggles default-identity-absent, and "no system message" versus "empty system message" are different baselines.
- 2026-07-27: [minefield-doctor](../doctor/) shipped: one stdlib file that diagnoses any OpenAI-compatible endpoint against the registry, tested on five lanes across llama.cpp, vLLM, and MLX. Trap [29](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) landed measured: the server's reasoning-off flag is a default, not a gate.
- 2026-07-27: traps [21](../traps/versioning/21-no-generation-config-server-defaults-win.md) and [22](../traps/evaluation/22-family-card-budget-floors-differ-by-size.md), both measured on our fleet: a checkpoint with no generation_config.json silently runs your server's built-in sampling, and thinking budget floors differ by size within one model family.
- 2026-07-27: six new reported-by-others traps ([23](../traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md) through [28](../traps/runtime/28-mtp-fails-only-under-concurrency-or-temperature.md)) mined from upstream issue trackers and community template work, every source read and verified before writing: streaming answer routing, C++ Jinja portability, empty think-block cache poisoning, tool-call-inside-think, NVFP4 accuracy cliffs, MTP concurrency failures. First Qwen-upstream and DeepSeek-runtime coverage.
- 2026-07-27: trap [20](../traps/reasoning/20-reasoning-write-field-name-diverges.md), the reasoning write field is runtime-specific (found by @Defilan while replicating trap 04 on llama.cpp); trap 04's fix section now names the correct field per runtime.
- 2026-07-27: contribution overhaul: easy-door issue form, per-model index, maintainer workflow, finder named at the top of every entry.
- 2026-07-27: twelve new traps ([08](../traps/runtime/08-image-toolchain-newer-than-driver.md) through [19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md)) covering runtime, quantization, memory, evaluation, versioning, and tools; category structure; hall of fame.
- 2026-07-27: launched with seven traps and [checks/preflight_template.py](../checks/preflight_template.py).

Full history in [CHANGELOG.md](../CHANGELOG.md). New entries land as they are
verified; issue reports get a first maintainer response within a few days.

## Methodology preamble

Three rules apply to every entry and to every number you publish about a
served model.

**1. Inspect the assembled prompt, not the request.** Most of these traps
live between a correct-looking request and a correct-looking response. The
only place they are visible is what the server actually renders and runs.

**2. State build AND revision next to every number.** Thinking policy
differs by build, not just revision. FP8 and NVFP4 uploads of the same model
at the same revision have been measured applying different thinking policies
on the wire (@quantumleap68, logging proxy). A published rate that names a
revision without its build is underspecified; treat cross-build comparisons
as cross-model until shown otherwise. The unit under test is
image + weights + hardware + build, never "the model".

**3. Diff the kwarg surface in both directions.** Enumerate every kwarg the
template reads and diff against the model card, and diff the parameters the
API accepts against what the template reads. Read-but-undocumented is an
untested variable (trap 04's control); accepted-but-unread is a dead knob
(trap 07).

## Scope

Entries so far come from characterizing models on DGX Spark class hardware
(vLLM, llama.cpp, EXL3-tail containers), from a stock mlx_lm lane on Apple
silicon, from a quad-P100 llama.cpp fleet
(@apollo-mg), a Strix Halo box (@Defilan), a systematic recipe grid
(@mrpmorris), and a multi-host MoE training and evaluation campaign on
RTX PRO 6000 class hardware (@Hikari_07_jp). Template, scoring, and toolchain classes should be assumed
present on other stacks until checked. Revisions and builds are named per
entry. Much of the raw evidence lives in the
[Laguna S 2.1 testing lab](https://github.com/Blackwellboy/laguna-s21-lab).

## Checks you can run

[`checks/preflight_template.py`](../checks/preflight_template.py): stdlib-only
template forensics. Renders a marked three-turn conversation through your
serving path and reports whether prior-turn reasoning is preserved or
stripped (trap 04), whether the template injects or rewrites messages, and
which kwargs the template actually reads versus what the card documents
(traps 04 and 07). See [`checks/README.md`](../checks/README.md).

## License

MIT (see [LICENSE](../LICENSE)). Entries describe measurements and checks; no
model weights are included.

## Support

- GitHub Sponsors: <https://github.com/sponsors/Blackwellboy>
- Buy Me a Coffee: <https://buymeacoffee.com/blackwellboy>

## Community impact

Adoptions, contributor discoveries and independently verifiable outcomes:
[community/COMMUNITY_IMPACT.md](../community/COMMUNITY_IMPACT.md).


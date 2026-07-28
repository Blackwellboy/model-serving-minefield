# Model Serving Minefield

You just lost hours to a "model problem" that turned out to be a serving or
config bug. You are not crazy, and you are not the first: this is the registry
where those bugs live, so the next person loses minutes instead of an evening.

Every entry here produced a **confidently wrong measurement** on a real
serving path: chat templates, tool parsers, reasoning fields, quantization
kernel paths, container toolchains, memory allocation, eval harnesses,
versioning. The common shape: the request looks correct, the response looks
correct, and the number is still wrong, because something happened between
the two that nobody inspected. Request-shaped checks cannot catch any of
these.

Each entry leads with the symptom you would actually observe, then the
mechanism, the stacks and builds it bit, the check that catches it, and the
fix. Each carries a status: **reproduced here** (measured in our lab, raw
linked), **reported by others** (credited and linked, not independently
reproduced), or **under test**. Reported-but-unreproduced entries are
welcome here and labelled, not rejected.

In a hurry? [Run the doctor](#run-the-doctor) against your own endpoint. It
has checks for **17 of these 74 entries** and runs in under a minute. It is
not a broad bill of health, and it prints its own coverage line at the end of
every run so you can see exactly how much of the registry it touched, how
much it could not check on your stack, and how much it never implements.

## Find your symptom

| You are seeing | It may be | Entry | Status |
|---|---|---|---|
| Firing rate reads 0% while the model visibly reasons | Wrong reasoning field name | [01](traps/reasoning/01-reasoning-field-two-names.md) | reproduced here |
| Every response starts with a stray `</think>` | Parser strips the open tag, not the close | [02](traps/template/02-orphaned-think-close-tag.md) | reproduced here |
| Two testers, "same model", different behavior | Thinking-kwarg default drifts by revision and upload | [03](traps/reasoning/03-enable-thinking-default-drift.md) | reproduced here |
| Thinking fires single-turn, collapses multi-turn | Reasoning stripped from replayed history | [04](traps/template/04-history-reasoning-stripping.md) | reproduced here |
| Verdicts flip on characters nobody looked at | Scorer normalization (curly quotes, unicode) | [05](traps/evaluation/05-scorer-normalization-verdict-flip.md) | reported by others |
| Thinking dies under any real system prompt | System-prompt topology moves the gate (which end carries the lever is stack-dependent) | [06](traps/reasoning/06-identity-sentence-eviction.md) | reported by others; the reported prefix-key mechanism did NOT reproduce on a second stack |
| Thinking dies under an agent prompt with tool schemas specifically | Possibly nothing: the gate is conditioned on apparatus and task, and a 752-byte agent prompt with 3 tool schemas fired 90.4% at n=492 | [06 (apparatus route)](traps/reasoning/06-identity-sentence-eviction.md#if-you-arrived-here-with-an-agent-prompt-and-tools) | contributor-measured, conditions as reported |
| `reasoning_effort` levels change nothing | Template never reads the parameter | [07](traps/reasoning/07-reasoning-effort-silently-ignored.md) | reproduced here |
| Healthy load, then death at kernel build or first token | Image toolchain newer than host driver (error 222 class) | [08](traps/runtime/08-image-toolchain-newer-than-driver.md) | reproduced here |
| Same weights work/fail/crawl depending on nothing obvious | Container image decides the kernel path | [09](traps/runtime/09-image-choice-changes-outcome.md) | reproduced here |
| "FP4" checkpoint far slower than the format promises | Quant label routes to a weight-only fallback | [10](traps/quantization/10-quant-label-is-not-the-kernel-path.md) | reproduced here |
| Model got slower after raising speculative depth | Acceptance collapses past the drafter's depth | [11](traps/runtime/11-speculative-depth-peak-and-collapse.md) | reproduced here |
| Hard tasks return HTTP 200 with empty content (or a missing content key) | Thinking ate the whole token budget | [12](traps/evaluation/12-empty-content-at-token-ceiling.md) | reproduced here |
| Unified-memory box at 98% RAM, or capacity stranded | Utilization fraction reserving against the OS's pool | [13](traps/memory/13-utilization-fraction-on-unified-memory.md) | measured here, raw not published |
| Finetune/abliterated swap changed more than behavior | Re-upload is a different artifact, shards and drafter included | [14](traps/versioning/14-finetune-reupload-not-drop-in.md) | measured here, raw not published |
| Multiple-choice evals hang or score near zero | Server lacks echo+logprobs; lm-eval wedges | [15](traps/evaluation/15-no-echo-logprobs-wedges-lm-eval.md) | reported by others |
| Scores move when you re-bucket cap-hits | finish_reason used as a pass/fail signal | [16](traps/evaluation/16-finish-reason-is-not-a-failure-signal.md) | reported by others + reproduced here |
| Clean A/B effect that will not replicate | Each arm ran its own "recommended" sampling | [17](traps/evaluation/17-per-arm-recommended-sampling-confound.md) | reported by others + reproduced here |
| Decode collapses with depth, shallow bench fine | Flash attention off; penalty grows with depth | [18](traps/runtime/18-flash-attention-off-halves-deep-decode.md) | reported by others |
| Model "cannot tool-call", describes calls in prose | Server template/parser flags; native schema dropped | [19](traps/tools/19-missing-jinja-breaks-tool-parsing.md) | reported by others |
| Trap 04's fix "does not work", render still stripped | Reasoning resent under the wrong write field for the runtime | [20](traps/reasoning/20-reasoning-write-field-name-diverges.md) | contributor-measured + reproduced here; behavioral half under test |
| One client's requests think and blow budgets on a reasoning-off lane | Server thinking flag is a default, not a gate; client kwarg overrides | [29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) | reproduced here |
| Your "model defaults" differ from everyone else's | Checkpoint ships no generation_config; server built-ins win | [21](traps/versioning/21-no-generation-config-server-defaults-win.md) | reproduced here |
| Sibling model empty at the family's "safe" token budget | Thinking budget floor differs by size within a family | [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md) | reproduced here (published 40-sample map) + measured here, raw not published (the per-size claim) |
| Streamed replies blank, non-streamed fine | Answer routed into reasoning deltas, content empty | [23](traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md) | reported by others |
| Tools broken on llama.cpp/LM Studio, fine on vLLM | Official template uses Python-only Jinja constructs | [24](traps/template/24-official-template-breaks-cpp-jinja.md) | reported by others |
| Prefix cache misses, junk empty think pairs in history | Template emits think wrappers for empty reasoning | [25](traps/template/25-empty-think-blocks-poison-prefix-cache.md) | reported by others |
| Agent ends with stop, raw text has a full tool call | Tool call emitted inside unclosed think; parser eats it | [26](traps/tools/26-tool-call-inside-unclosed-think.md) | reported by others |
| NVFP4 model fast but suddenly "does not know basics" | Quant ignore-list miss or version-scoped kernel path | [27](traps/quantization/27-nvfp4-accuracy-cliff-config-misses.md) | reported by others |
| MTP lane green in bench, hangs/crashes in production | Speculative fails only under concurrency or mid temperature | [28](traps/runtime/28-mtp-fails-only-under-concurrency-or-temperature.md) | reported by others |
| Every system-prompt condition differs from bare, on every axis at once | Template's default system message is replaced wholesale by any caller system message | [30](traps/template/30-default-system-message-silently-replaced.md) | reproduced here |
| Historical eval score nobody can regenerate, far above the committed engine | Leftover oracle re-ranker wrote into the honest metrics namespace | [31](traps/evaluation/31-leftover-oracle-reranker.md) | measured here, raw not published |
| A client request runs past the server's --max-tokens launch flag | mlx_lm's flag is a per-request default, not a ceiling | [32](traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md) | reproduced here |
| You gave a MoE more active experts and it got *worse* | Renormalization dilutes the original top-8; selection is intact | [33](traps/routing/33-moe-inference-topk-expansion-tax.md) | reported by others |
| A clean significant win that evaporates against the shipped model | The baseline is a configuration you degraded yourself | [34](traps/evaluation/34-baseline-you-degraded-yourself.md) | reported by others |
| Same weights and items, different score on a re-run (any box, even the same process) | Item agreement is 97.6% to 98.7%, not 100%; the machine is not the variable | [35](traps/evaluation/35-identical-weights-do-not-score-identically.md) | reproduced here |
| Multiple-choice collapses, or two arms truncate at wildly different rates | The token cap binds differently per arm | [36](traps/evaluation/36-token-cap-is-an-arm-level-handicap.md) | reported by others |
| A benchmark reads zero for every arm, with zero infra errors | Harness fault, not model inability | [37](traps/evaluation/37-uniform-zero-is-a-harness-verdict.md) | reported by others |
| Offline rollouts parse as malformed, interactive output is fine | The template supplies the opening think tag, the model does not | [38](traps/template/38-template-owns-the-opening-think-tag.md) | reported by others |
| Output is complete gibberish after a previously working run | `device_map="auto"` spilled the model onto a device you excluded | [39](traps/runtime/39-device-map-auto-offloads-and-returns-garbage.md) | reported by others |
| Contamination gate removes a third of your corpus | One boilerplate n-gram, or a gram too short for the alphabet | [40](traps/evaluation/40-ngram-decontamination-false-positives.md) | reported by others |
| Batched the loop, GPU hit 100%, the job took exactly as long | A static batch waits for its longest sequence | [41](traps/runtime/41-static-batching-buys-power-not-throughput.md) | reported by others |
| Adding an agent prompt and tool schemas drops your benchmark score hard | Tool-call exits are being scored as wrong answers | [42](traps/evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md) | contributor-measured, conditions as reported |
| Agent emits `<function=NAME></function>` with no arguments, then loops | Template gates tool args on `is mapping` with no `else`, so replayed JSON-string args render empty | [43](traps/template/43-tool-args-string-not-mapping.md) | contributor-measured, conditions as reported |
| Offline dequant reads cosine 0.92 and the model answers "9.9 vs 9.11" as "9 and 9" | Scales stored linear but read swizzled, so the damage is distributed rather than obvious | [44](traps/quantization/44-fp4-dequant-scale-swizzle-layout.md) | contributor-measured, conditions as reported |
| Prefill drops ~20x for one KV quant pair and the bench tool prints a clean table | Flash-attention kernels were never compiled for that pair, so it silently leaves the fast path | [45](traps/quantization/45-fa-all-quants-cpu-fallback.md) | contributor-measured, conditions as reported |
| High GPU utilization at low power draw, and decode ~2.5x below spec | The running binary predates its own arch-native kernel; the fix was merged but never rebuilt | [46](traps/versioning/46-stale-build-missing-arch-kernel.md) | contributor-measured, conditions as reported |
| Time-to-first-token stays flat as an agent conversation grows | The engine auto-disabled prefix caching for a hybrid or recurrent arch and said so once, at startup | [47](traps/runtime/47-prefix-caching-autodisabled-hybrid.md) | contributor-measured, conditions as reported |
| Every request takes ~30s including cache hits, but the server log says it finished in seconds | A `.local` name resolving dual-stack with a dead IPv6 route; the tax is entirely client-side | [48](traps/routing/48-dual-stack-mdns-latency-tax.md) | contributor-measured, conditions as reported |
| A clean, reproducible performance gap that collapses when the harness is fixed | The benchmark prompt never tokenized to the length the table claims | [49](traps/evaluation/49-prompt-not-tokenized-to-target.md) | contributor-measured, conditions as reported |
| Per-layer parity says the final layer exploded and you are ~4.5x off | Dump conventions differ: an off-by-one layer index plus pre-norm compared against post-norm | [50](traps/evaluation/50-hidden-state-dump-convention.md) | contributor-measured, conditions as reported |
| Perplexity is NaN on one backend and clean on the others with the same file | A fused matmul path on that backend, not a property of the quantization format | [51](traps/quantization/51-single-backend-nan-fused-path.md) | contributor-measured, conditions as reported |
| An impressive, stable throughput number that evaporates when a correctness gate lands | The fast path was skipping required work, so the broken config is the one that wins | [52](traps/evaluation/52-speed-measured-on-a-broken-config.md) | contributor-measured, conditions as reported |
| You changed a flag, restarted, and the old behavior is still there | A stale process kept the port; the restart reported success and the replacement crash-looped | [53](traps/runtime/53-config-edit-never-took-effect.md) | contributor-measured, conditions as reported |
| A clean +20% speedup that also reproduces on a build without the feature | Run order, warm caches or cross-session drift; what you varied was not the only thing that varied | [54](traps/evaluation/54-run-order-and-warm-cache-artifacts.md) | contributor-measured, conditions as reported |
| A model serves happily at its advertised context and scores badly on long-context retrieval | Advertised, served and trained context are three different numbers | [55](traps/evaluation/55-supported-context-is-not-trained-context.md) | contributor-measured, conditions as reported |
| Template forensics reports "no chat template" on a model that chats fine | The template is Python code inside the checkpoint, not a Jinja file | [56](traps/template/56-checkpoint-ships-no-chat-template.md) | reproduced here |
| You sent the thinking kwarg as the string `"false"` and thinking turned on | The kwarg is evaluated for truthiness, not parsed as a boolean | [57](traps/reasoning/57-thinking-kwarg-truthiness-coercion.md) | reproduced here |
| A reasoning-off lane returns empty content, but only to the client that set `reasoning_effort` | The parameter is an undocumented thinking switch and injects a hidden preamble | [58](traps/reasoning/58-reasoning-effort-injects-hidden-preamble.md) | reproduced here |
| The model quotes its own earlier reasoning, fluently, and the quote is invented | History reasoning is stripped before render and no field name gets it back | [59](traps/reasoning/59-reasoning-roundtrip-confabulation.md) | reproduced here |
| A long-context test fails, then passes on an immediate re-run with nothing changed | A cold prefill and a prefix-cache hit do not return the same answer | [60](traps/runtime/60-cold-prefill-and-cache-hit-disagree.md) | measured here, raw not published |
| A million-token window accepts your prompt, counts it exactly, and answers from nowhere near the start | Advertised, trained and served context are three different numbers, and none of them is the usable one | [61](traps/evaluation/61-advertised-window-fails-silently.md) | reproduced here (the three-ceiling arithmetic) + measured here, raw not published (the depth curve) |
| Mostly-correct output carrying fragments of special-token syntax that are not valid tokens | A speculative-decode drafter configuration garbling the markup dialect | [62](traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md) | reproduced here (the fixed config and the check) + measured here, raw not published (the failure) |
| Multi-turn quality drops with depth, and the fix the template documents changes nothing | The reasoning round trip has one correct shape out of four: right field name AND an inverted-polarity gate | [63](traps/reasoning/63-reasoning-round-trip-one-correct-shape.md) | reproduced here |
| HTTP 200, `finish_reason: stop`, a complete answer, and `content` is null | Request keyword and in-text toggle disagree, so the whole answer is delivered as reasoning | [64](traps/reasoning/64-answer-lands-in-reasoning-on-toggle-conflict.md) | reproduced here |
| You raised the token budget and content is still empty | The rescue is a kwarg the template never reads, documented only in the parser's docstring | [65](traps/reasoning/65-parser-only-rescue-kwarg.md) | reproduced here |
| A file path in your prompt comes back missing a directory component | The template scans user text for `/think` and `/no_think`, obeys them, and deletes them | [66](traps/template/66-in-text-thinking-toggle-mutates-user-text.md) | reproduced here |
| Multi-turn is worse than single-turn and the prompt contains Python-looking text | The server normalises message content to a list and the template renders the list repr | [67](traps/template/67-history-rendered-as-object-repr.md) | reproduced here |
| A multimodal prompt behaves as though your text and image were in the other order | Content-part order is discarded and adjacent text parts are glued together | [68](traps/template/68-multimodal-part-order-discarded.md) | reproduced here |
| Assertions on rendered output fail on whitespace and roles you did not send | Three small template defects sharing one cause: guards written for a case the template cannot reach | [69](traps/template/69-minor-template-defects.md) | reproduced here |
| Reasoning arrives unparsed no matter which `--reasoning-parser` you name | The parser ships inside the checkpoint and is bundled with no serving stack | [70](traps/runtime/70-in-repo-parser-not-bundled.md) | reproduced here |
| You grepped the config for the speculative setting and it is not there | One MTP layer does not mean one draft token, and the key is not called what you will grep for | [71](traps/runtime/71-mtp-config-key-and-draft-count.md) | reproduced here (the config key) + measured here, raw not published (the draft count) |
| Your monitoring pages on 5xx every time a user sends a bad image URL | A caller's bad media path is reported as a server fault | [72](traps/runtime/72-media-fetch-errors-are-5xx.md) | reproduced here |
| You cannot work out what the image in that request cost you | Multimodal token cost is not attributable from the usage block | [73](traps/evaluation/73-multimodal-token-cost-not-attributable.md) | measured here, raw not published |
| A model confidently captions audio that contains nothing to caption | Out-of-domain audio is answered from a memorised annotation schema | [74](traps/evaluation/74-non-speech-audio-fabricated-captions.md) | measured here, raw not published |

If you run one check from this registry, make it
[Trap 04](traps/template/04-history-reasoning-stripping.md). It is the one
whose symptom looks most like a genuine model property, and it cost four
independent testers a combined multi-week detour.

About to serve a specific model? The
[per-model index](models/README.md) maps model families to the traps
observed on them.

## Run the doctor

One stdlib-only file, no install, that diagnoses your endpoint against
17 of this registry's 74 entries in under a minute:

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
["I hit a trap" form](../../issues/new?template=report-a-trap.yml). Full
safety story, check list and coverage caveats in
[doctor/README.md](doctor/README.md).

## Before you serve a new model

The one-line checklist, each line backed by an entry. Lines 2, 3, 4, 5 and
the first two thirds of line 8 have a check in [the doctor](doctor/); lines
1, 6, 7 and the echo-and-logprobs part of line 8 do not, and are yours to
run. Runnable pieces also live in [checks/](checks/).

1. Image toolchain matches the host driver ([08](traps/runtime/08-image-toolchain-newer-than-driver.md)); record the image digest ([09](traps/runtime/09-image-choice-changes-outcome.md)).
2. Read `config.json`'s quant schemes, not the repo name ([10](traps/quantization/10-quant-label-is-not-the-kernel-path.md)).
3. One tool-defined request returns a structured `tool_calls` array ([19](traps/tools/19-missing-jinja-breaks-tool-parsing.md)).
4. Both reasoning field names read, positive control fires ([01](traps/reasoning/01-reasoning-field-two-names.md)), thinking kwarg sent explicitly ([03](traps/reasoning/03-enable-thinking-default-drift.md)).
5. Assembled prompt inspected at turn 3 with a marked reasoning string ([04](traps/template/04-history-reasoning-stripping.md); [checks/preflight_template.py](checks/preflight_template.py) automates it).
6. Attention implementation confirmed on, benchmarked at real depth ([18](traps/runtime/18-flash-attention-off-halves-deep-decode.md)).
7. KV sized in bytes on unified memory ([13](traps/memory/13-utilization-fraction-on-unified-memory.md)); speculative K swept, not searched ([11](traps/runtime/11-speculative-depth-peak-and-collapse.md)).
8. Scores bucketed on extractable output, ceilings of at least 8192, echo+logprobs probed before multiple-choice evals ([16](traps/evaluation/16-finish-reason-is-not-a-failure-signal.md), [12](traps/evaluation/12-empty-content-at-token-ceiling.md), [15](traps/evaluation/15-no-echo-logprobs-wedges-lm-eval.md)).

## Categories

| Directory | Covers |
|---|---|
| [traps/template/](traps/template/) | Chat templates, history assembly, prompt rendering |
| [traps/tools/](traps/tools/) | Tool calling, parsers, structured output |
| [traps/reasoning/](traps/reasoning/) | Reasoning fields, thinking kwargs and control |
| [traps/quantization/](traps/quantization/) | Quant formats, precision, kernel paths |
| [traps/routing/](traps/routing/) | MoE expert routing and activation config (top-k, gate weighting) |
| [traps/runtime/](traps/runtime/) | CUDA and toolchains, container images, attention and speculative config |
| [traps/memory/](traps/memory/) | KV cache, memory allocation, context windows |
| [traps/evaluation/](traps/evaluation/) | Harness traps, scoring, budgets, confounds |
| [traps/versioning/](traps/versioning/) | Revisions, builds, re-uploads, distribution |

Old flat paths (`traps/NN-*.md`) remain as redirect stubs so existing links
keep resolving.

## How to contribute

Two doors. Take the easy one; it counts just as much.

- **Easy door: you hit a trap, tell us in plain words.** Open an
  ["I hit a trap" issue](../../issues/new?template=report-a-trap.yml). Four
  plain questions, no formatting, no writeup. A maintainer verifies what can
  be verified, writes the entry, credits you by name, and links your issue.
  Most entries should start this way.
- **Full door: write the entry yourself.** One file under the right
  `traps/<category>/`, format and evidence bar in
  [CONTRIBUTING.md](CONTRIBUTING.md), PR template walks the checklist.

Not sure whether what you hit is a trap or your own mistake? Open the issue
anyway. "I could not tell whether this was me or the stack" is exactly the
state these entries exist to resolve, and triage is cheap.

How reports become entries, and how statuses are assigned, is documented in
[MAINTAINING.md](MAINTAINING.md). Candidates that were tested and did not
(or could not) promote are recorded in [mining/](mining/); a negative is
information too.

## Contributors

Findings in this registry come from **@quantumleap68**,
**TheTom** ([offlabel](https://github.com/TheTom/offlabel)),
**@Defilan**, **@apollo-mg**,
**@mrpmorris** ([sparkrun-recipes](https://github.com/mrpmorris/sparkrun-recipes)),
**eugr** ([spark-vllm-docker](https://github.com/eugr/spark-vllm-docker)),
**@Hikari_07_jp** ([qwen36-a6b](https://github.com/hikarioyama/qwen36-a6b)),
and **Blackwellboy** ([laguna-s21-lab](https://github.com/Blackwellboy/laguna-s21-lab)).
Per-finding credit is in [HALL_OF_FAME.md](HALL_OF_FAME.md), and every entry
names its finder at the top. Contributors are always named unless they ask
otherwise.

## Recently added

- 2026-07-28: **traps [63](traps/reasoning/63-reasoning-round-trip-one-correct-shape.md) through [74](traps/evaluation/74-non-speech-audio-fabricated-captions.md): the NVIDIA Nemotron 3 family**, three checkpoints including this registry's first multimodal lane, characterised across three sessions and merged. Headline: the reasoning round trip has exactly **one correct shape out of four**, because the preservation gate is named `truncate_history_thinking` and **true means discard**, the opposite polarity to the name this registry already documents, so a pipeline standardised on the other one silently no-ops. Also: a template that scans user text for `/think` and `/no_think`, obeys them over the documented keyword, and deletes them from the prompt, so any path or URL containing those characters is silently rewritten. Eight more findings landed as **additions to existing entries** rather than new numbers, including a measured empty-content floor and the proof that no single floor is safe to copy.
- 2026-07-28: **traps [56](traps/template/56-checkpoint-ships-no-chat-template.md) through [62](traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md): first coverage of a DeepSeek-V4-Flash serving path**, measured at request level against a live two-node lane. The checkpoint ships no chat template at all, only Python; the thinking kwarg is evaluated for truthiness so the string `"false"` turns thinking on; `reasoning_effort` is an undocumented thinking switch that also injects a hidden preamble, and only at the top level; prior-turn reasoning is discarded by every field name and the model confabulates it back on request; a cold prefill and a prefix-cache hit answer the same prompt differently; and the advertised million-token window rests on a 64K trained base with nothing anywhere reporting the difference. Full serving path and the traps in one place on the [model page](models/deepseek-v4-flash.md). A pre-registered experiment that would separate the cache result's two candidate mechanisms is written but [NOT RUN](mining/2026-07-28-chunked-prefill-vs-cache-replay-experiment.md), because it needs a serve change and the lane is production.
- 2026-07-28: **traps [43](traps/template/43-tool-args-string-not-mapping.md) through [55](traps/evaluation/55-supported-context-is-not-trained-context.md): the registry's first large external contribution**, thirteen entries from [@TheTom](https://github.com/TheTom), who maintains the offlabel operator guide. All land at **contributor-measured, conditions as reported**: he measured every one on his own hardware and stated the conditions, and we have not reproduced them here. Headline classes: a chat template that renders replayed tool arguments empty when they arrive as a JSON string, an FP4 dequant that reads its scales in the wrong layout so the damage is distributed rather than obvious, KV-quant pairs with no compiled flash-attention kernel, a binary that predates its own arch-native kernel, prefix caching silently auto-disabled on hybrid architectures, and a run of measurement traps that each produced a clean reproducible number that was not real. **Numbering is provisional**; see [MAINTAINING.md](MAINTAINING.md#numbering-in-this-merge).
- 2026-07-28: trap [42](traps/evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md): a single-turn eval harness scores `finish_reason=tool_calls` as a wrong answer, so attaching an agent prompt and tool schemas costs measured score without costing capability. Found and measured at n=492 by [@apollo-mg](https://github.com/TheTom/offlabel/pull/10#issuecomment-5093534067) with raw published: pooled pass@1 fell 18.9 points while wrong answers moved by one and accuracy conditional on attempting held at 91.71%. Carries the two detection fingerprints (conditional against pooled; bucket by exit path, not by score) and a pre-registered open question, with both predictions on record, about whether the termination benefit survives tool output being fed back.
- 2026-07-28: nine traps ([33](traps/routing/33-moe-inference-topk-expansion-tax.md) through [41](traps/runtime/41-static-batching-buys-power-not-throughput.md)) mined from [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)'s public research log on expanding a pretrained MoE's inference top-k, offered by him for this purpose. Headline: raising a MoE's active-expert count from 8 to 32 costs accuracy before any training, silently, because renormalization dilutes the original top-8 rather than adding to it. New [routing/](traps/routing/) category for MoE activation config. The rest are measurement traps that made real numbers wrong: a baseline you degraded yourself, identical weights not scoring identically, token caps binding unequally per arm, all-arms-zero as a harness verdict, the opening think tag the template owns, `device_map="auto"` spilling silently, contamination screens firing on boilerplate, and static batching buying power instead of throughput.
- 2026-07-27: trap [32](traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md): mlx_lm's server `--max-tokens` flag is a per-request default, not a cap; a client can quietly run past it. Same pass landed MLX-scoped sections in six existing entries (mlx_lm now has real coverage in the [per-stack index](models/README.md)) and the new [mining/](mining/) verification-notes area for candidates that did not or could not promote.
- 2026-07-27: trap [31](traps/evaluation/31-leftover-oracle-reranker.md): a leftover oracle re-ranker (a debugging script that boosts candidates by expected id or looks them up by the answer's file name stem) turns a failing retrieval eval into a passing one, and the inflated number outlives the script; with the two detection fingerprints (top-1 equals top-3 exactly; saturation at exactly 1.0) and a copyable no-oracle negative control.
- 2026-07-27: trap [30](traps/template/30-default-system-message-silently-replaced.md): the template's default system message vanishes the moment you send your own, so every with-system-prompt condition also toggles default-identity-absent, and "no system message" versus "empty system message" are different baselines.
- 2026-07-27: [minefield-doctor](doctor/) shipped: one stdlib file that diagnoses any OpenAI-compatible endpoint against the registry, tested on five lanes across llama.cpp, vLLM, and MLX. Trap [29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) landed measured: the server's reasoning-off flag is a default, not a gate.
- 2026-07-27: traps [21](traps/versioning/21-no-generation-config-server-defaults-win.md) and [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md), both measured on our fleet: a checkpoint with no generation_config.json silently runs your server's built-in sampling, and thinking budget floors differ by size within one model family.
- 2026-07-27: six new reported-by-others traps ([23](traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md) through [28](traps/runtime/28-mtp-fails-only-under-concurrency-or-temperature.md)) mined from upstream issue trackers and community template work, every source read and verified before writing: streaming answer routing, C++ Jinja portability, empty think-block cache poisoning, tool-call-inside-think, NVFP4 accuracy cliffs, MTP concurrency failures. First Qwen-upstream and DeepSeek-runtime coverage.
- 2026-07-27: trap [20](traps/reasoning/20-reasoning-write-field-name-diverges.md), the reasoning write field is runtime-specific (found by @Defilan while replicating trap 04 on llama.cpp); trap 04's fix section now names the correct field per runtime.
- 2026-07-27: contribution overhaul: easy-door issue form, per-model index, maintainer workflow, finder named at the top of every entry.
- 2026-07-27: twelve new traps ([08](traps/runtime/08-image-toolchain-newer-than-driver.md) through [19](traps/tools/19-missing-jinja-breaks-tool-parsing.md)) covering runtime, quantization, memory, evaluation, versioning, and tools; category structure; hall of fame.
- 2026-07-27: launched with seven traps and [checks/preflight_template.py](checks/preflight_template.py).

Full history in [CHANGELOG.md](CHANGELOG.md). New entries land as they are
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

[`checks/preflight_template.py`](checks/preflight_template.py): stdlib-only
template forensics. Renders a marked three-turn conversation through your
serving path and reports whether prior-turn reasoning is preserved or
stripped (trap 04), whether the template injects or rewrites messages, and
which kwargs the template actually reads versus what the card documents
(traps 04 and 07). See [`checks/README.md`](checks/README.md).

## License

MIT (see [LICENSE](LICENSE)). Entries describe measurements and checks; no
model weights are included.

## Support

- GitHub Sponsors: <https://github.com/sponsors/Blackwellboy>
- Buy Me a Coffee: <https://buymeacoffee.com/blackwellboy>

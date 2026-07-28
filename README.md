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
fix. Each carries exactly one status from a
[closed vocabulary](CONTRIBUTING.md#status-vocabulary), and the status says how
much weight the entry carries: **reproduced here** (we ran it, and you can
check the result without asking us for anything), **contributor-measured,
conditions as reported** (someone else measured it and published their
conditions), **reported by others** (credited and linked, not independently
reproduced), **measured here, raw not published** (we ran it, and you cannot
check it), and **under test**. Entries that are reported, contributed or
unreproduced are welcome here and labelled, never rejected; what the label
protects is your ability to tell them apart at a glance.

## Start here

Four doors, and which one you want depends on why you are here. Ninety-seven
entries is too many to read; none of these asks you to.

- **"What am I doing?"** The **[playbooks](playbooks/)** are ordered checklists
  for the four jobs people actually arrive with:
  [before you publish an A/B](playbooks/before-you-publish-an-ab.md),
  [thinking died when I made it multi-turn](playbooks/thinking-died-multi-turn.md),
  [porting a harness to a new server](playbooks/porting-a-harness.md), and
  [long context looks broken](playbooks/long-context-looks-broken.md). Each step
  names the entry it guards against and the check to run. Nothing in them is
  new; they are the existing entries, sequenced.
- **"What am I running?"** The **[per-stack pages](stacks/)** give you the five
  entries most likely to bite on
  [vLLM](stacks/vllm.md), [llama.cpp and GGUF](stacks/llama-cpp.md),
  [Ollama](stacks/ollama.md) or [mlx_lm](stacks/mlx.md), plus the three checks
  to run before anything else. The
  **[per-model and per-stack index](models/README.md)** is the full map,
  including layers that are not serving stacks. Absence from either means
  nobody has reported on that model here, not that it is safe.
- **"What am I seeing?"** The **[symptom table](#find-your-symptom)** is
  directly below, all 97 entries, one row each, sorted by number. It is the
  answer to a weird number you are holding right now. That is the premise of
  this registry and it has not moved; it is placed after these doors only
  because most visitors arrive before the symptom rather than during it.
- **"What should I read first?"** The **[Core 12](CORE.md)**, chosen on
  evidence of what has cost people evenings rather than on which entries have
  the best data. Everything else is Extended, which means specific rather than
  lesser.

In a hurry and holding an endpoint? [Run the doctor](#run-the-doctor) against
it. It is a **thinking-stack preflight, not a minefield doctor**: it has checks
for **18 of these 97 entries**, weighted toward reasoning fields, templates and
tool parsing, and a clean run from it says nothing about the other 79. It runs
in under a minute and prints its own coverage line at the end of every run so
you can see exactly how much of the registry it touched, how much it could not
check on your stack, and how much it never implements.

**Things that did not work out** are collected in [mining/](mining/): the
candidates we tested that **did not reproduce**, the ones that are **blocked or
not testable** on the lanes available, and the ones that are **specification
only, not run**. A negative is information, and it is often the fastest way to
stop chasing a ghost somebody else already chased.

## Find your symptom

All 97 entries. If you know what you are running rather than what you are
seeing, the [per-model index](models/README.md) is the shorter route.

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
| You gave a MoE more active experts and it got *worse* | Renormalization dilutes the original top-8; selection is intact | [33](traps/routing/33-moe-inference-topk-expansion-tax.md) | reported by others + measured here, raw not published |
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
| A clean +20% speedup that also reproduces on a build without the feature | Run order, warm caches or cross-session drift; what you varied was not the only thing that varied | [54](traps/evaluation/54-run-order-and-warm-cache-artifacts.md) | contributor-measured, conditions as reported (the framing rule alone is separately reproduced here) |
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
| A pinned install URL that worked for months returns 404 | The release asset was renamed, not withdrawn; the archive format changed | [75](traps/versioning/75-release-asset-renamed-pinned-url-404.md) | reproduced here |
| Startup logs that your only GPU is being skipped, then runs on the GPU | One bundled runner rejects the card at INFO before a later one accepts it | [76](traps/runtime/76-device-rejection-log-line-is-not-fatal.md) | reproduced here |
| Your thinking-off and thinking-on arms return byte-identical output at temperature 0 | Only one request field is validated; the rest are accepted and dropped | [77](traps/reasoning/77-only-one-request-field-is-validated.md) | reproduced here |
| You sent `tool_choice: "none"` and the agent called a tool anyway | The parameter is inert in both directions, and it fails open | [78](traps/tools/78-tool-choice-accepted-and-ignored.md) | reproduced here |
| HTTP 200, empty content, and a context size the model could never have honoured | An out-of-range context request is accepted with no clamp message | [79](traps/memory/79-out-of-range-context-request-accepted.md) | reproduced here |
| A decode rate thirty times the lane's ceiling, or a TTFT longer than the request | A reasoning parser batches the stream, so delta timings describe its flush schedule | [80](traps/runtime/80-reasoning-parser-batches-sse-deltas.md) | measured here, raw not published |
| A lane you just stopped leaves the next one dying at `cudaMemGetInfo` | Container exit and device memory reclaim are different events | [81](traps/memory/81-stopped-container-has-not-released-memory.md) | measured here, raw not published |
| Every turn misses the prefix cache, and the system prompt is not where you put it | The template relocates the system prompt onto the last user turn, so no two turns share a prefix | [82](traps/template/82-system-prompt-relocates-to-last-user-turn.md) | reproduced here |
| Your no-system-prompt control arm is not a control | The template injects a hard-coded default system prompt whenever the request omits one | [83](traps/template/83-template-carries-a-baked-default-system-prompt.md) | reproduced here |
| An agent loop returns HTTP 400 and the error blames the template, not your message list | A completed tool round trip followed by a user turn is unrenderable | [84](traps/template/84-tool-roundtrip-then-user-turn-is-unrenderable.md) | reproduced here |
| `enable_thinking` is rejected as a string and accepted as a boolean, on a model with no thinking at all | The server type-checks the kwarg by name even though the template never reads it | [85](traps/reasoning/85-enable-thinking-typechecked-though-never-read.md) | reproduced here |
| A prefilled assistant turn behaves differently from the same text mid-conversation | The final assistant message bypasses the template's assistant branch | [86](traps/template/86-final-assistant-turn-bypasses-the-template-branch.md) | reproduced here |
| `/props` reports a context length you did not launch with | It reports the PER-SLOT context, exposes no trained context, and calls itself disabled while serving | [87](traps/runtime/87-llamacpp-props-reports-per-slot-context.md) | reproduced here |
| You set `cache_prompt: false` to isolate a request and cannot tell whether it worked | On this build it does isolate, which is a third data point that does not reproduce two prior stacks | [88](traps/runtime/88-cache-prompt-false-does-isolate-here.md) | measured here, raw not published |
| Every arm of a quantisation ladder scores the same as the stock copy | An in-place weight edit mutated the stock copy too, through a shared inode | [89](traps/evaluation/89-hardlink-shard-pollution-invalidates-a-ladder.md) | contributor-measured, conditions as reported |
| A kernel library advertises a fast path your card cannot run, behind six errors that each look fixable | It ships cubins for one architecture only | [90](traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md) | contributor-measured, conditions as reported |
| A temperature-0 lane that passed a reproducibility check returns different answers under real traffic | Continuous batching is non-deterministic above a prompt-length floor, and a minimal reproduction is below it | [91](traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md) | reproduced here |
| A temperature-0 lane diverges at concurrency 1, where batching cannot be the cause | Partial prompt-cache hits are a second divergence source, and cache state outlives your arms | [92](traps/runtime/92-prompt-cache-is-a-second-divergence-source.md) | reproduced here |
| Moving the clock out of your system prompt changed nothing, or made reuse worse | The template relocates the system block, so the head of the prompt is the first user turn and the received mitigation is inverted | [93](traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md) | reproduced here |
| A reproducibility guarantee validated on one GPU does not hold on another, same binary and weights | Batch-invariant reproducibility is architecture-dependent past a few hundred prompt tokens | [94](traps/runtime/94-temp0-reproducibility-is-architecture-dependent.md) | reproduced here |
| You are about to caveat a number because another model shares the host | Two lanes on two GPUs of one host perturbed neither correctness nor decode, so the caveat is unearned | [95](traps/runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md) | measured here, raw not published |
| The serving binary reports more free VRAM than the card has in total | `--list-devices` prints host available memory as device free memory | [96](traps/memory/96-list-devices-reports-host-memory-as-device-free-memory.md) | reproduced here |
| A lane runs at a few percent of its achievable decode rate and nothing says why | Partial GPU offload, named by no log line and no `/props` field, with VRAM use no proxy for it | [97](traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md) | reproduced here |
| Output contains a stray ` /think` you never sent, breaking exact-match scoring | The mirror case: the template appends the marker to the last user message and it leaks | [66 (injection)](traps/template/66-in-text-thinking-toggle-mutates-user-text.md#the-mirror-case-injection-on-ollama) | reproduced here |

If you run one check from this registry, make it
[Trap 04](traps/template/04-history-reasoning-stripping.md). It is the one
whose symptom looks most like a genuine model property, and it cost four
independent testers a combined multi-week detour.

About to serve a specific model? The
[per-model index](models/README.md) maps model families to the traps
observed on them, and the [per-stack pages](stacks/) give you the five that
bite hardest on your serving stack plus the three checks to run first.

Holding a job rather than a symptom? The [playbooks](playbooks/) sequence
these entries into ordered checklists for publishing an A/B, recovering
multi-turn thinking, porting a harness, and diagnosing long context.

## Run the doctor

**Name it honestly: this is a thinking-stack preflight, not a minefield
doctor.** Its checks cluster on reasoning fields, chat templates, thinking
control, tool parsing and token ceilings, because that is where its
request-shaped probes can reach. It has nothing to say about quantisation
kernel paths, container toolchains, memory allocation, eval-harness confounds
or long-context behaviour, which is most of this registry. A clean run is a
statement about a handful of trap ids, never a bill of health.

With that said, one stdlib-only file, no install, that diagnoses your endpoint
against 18 of this registry's 97 entries in under a minute:

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
**@drowzeys** ([Keys](https://github.com/drowzeys)), **Exile**,
and **Blackwellboy** ([laguna-s21-lab](https://github.com/Blackwellboy/laguna-s21-lab)).
Per-finding credit is in [HALL_OF_FAME.md](HALL_OF_FAME.md), and every entry
names its finder at the top. Contributors are always named unless they ask
otherwise.

## Recently added

- 2026-07-28: **traps [91](traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md) through [97](traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md): the determinism axis, and the registry's first cross-architecture and co-tenancy coverage**, on the same llama.cpp lane as 82 to 88. The one to read is [91](traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md), because its failure mode is a **false negative**: temperature-0 divergence under concurrency needs a prompt above roughly 220 tokens, and the natural minimal reproduction is shorter than that, so the check passes and the lane is not deterministic. [93](traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md) is the one that corrects widely repeated advice: on a template that relocates the system block, a clock at the head of the system prompt is inert (136 cached tokens against 135), and moving it into the first user message, which is the usual remedy, is the single change that takes reuse from 77% to 0.6%. [94](traps/runtime/94-temp0-reproducibility-is-architecture-dependent.md) is a regime and not a ranking: `sm_86` and `sm_120` both diverge at 220 tokens, and only `sm_120` still diverges at 444. [95](traps/runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md) is a **negative** that removes a standing caveat, and it states the case it does not cover. [92](traps/runtime/92-prompt-cache-is-a-second-divergence-source.md) is a self-caught error: prompt-cache state survived across separate invocations against one process and inverted one of our own results before we found it.
- 2026-07-28: **traps [82](traps/template/82-system-prompt-relocates-to-last-user-turn.md) through [88](traps/runtime/88-cache-prompt-false-does-isolate-here.md): a fourth serving stack**, llama.cpp with `--jinja` against a Mistral-family Q8_0 GGUF of unstated provenance supplied by **Exile**. The checkpoint is deliberately not characterised and nothing here generalises to any named model. Headline: an agent loop of user, tool call, tool result, user is **unrenderable** and the 400 blames the template rather than your message list; and the template carries a hard-coded default system prompt injected whenever you omit one, so a no-system-prompt control arm **is not a control**. Also a negative worth as much as the positives: [88](traps/runtime/88-cache-prompt-false-does-isolate-here.md) finds `cache_prompt: false` DOES isolate on this build, a third data point that does not reproduce two prior stacks, and it lands with its build qualifier attached.
- 2026-07-28: traps [89](traps/evaluation/89-hardlink-shard-pollution-invalidates-a-ladder.md) and [90](traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md), from [@drowzeys](https://github.com/drowzeys) (Keys), shared from his public notes. An in-place weight edit that mutates the stock copy through a shared inode, so every comparison against it is quietly wrong; and a kernel library shipping cubins for one architecture only, behind six errors that each look like a fixable config bug. Two further findings of his landed inside traps [62](traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md) and [79](traps/memory/79-out-of-range-context-request-accepted.md) rather than taking numbers.
- 2026-07-28: trap [33](traps/routing/33-moe-inference-topk-expansion-tax.md) **promoted to reported by others + reproduced here.** The top-k expansion tax was landed from a research log whose every number is bf16 under HF transformers; it reproduces on our own **NVFP4** build, where under this registry's own rule a different quantisation is a different unit under test and the question was genuinely open. Monotone across four values of k, in two scoring protocols, on two independent passes each: k=8 to k=32 is **-4.50 points** at n=600 paired, discordant 37 against 10, exact McNemar **p = 9.8e-05**, with the independent replicate at -4.00 and p = 0.000936. [Method, both protocols and the runnable scripts](mining/2026-07-28-trap-33-q1-nvfp4-confirmed.md). **This is the second time a first-party run has confirmed an external contributor's finding here**, and as with the first, [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b) keeps the **Found by** line.
- 2026-07-28: **traps [75](traps/versioning/75-release-asset-renamed-pinned-url-404.md) through [81](traps/memory/81-stopped-container-has-not-released-memory.md): first Ollama coverage**, which [CONTRIBUTING](CONTRIBUTING.md#where-coverage-is-thin) had listed as a stack with no entries at all. The one with the highest operator cost is [77](traps/reasoning/77-only-one-request-field-is-validated.md): exactly one request field is validated, so a harness ported from another server sends `enable_thinking: false`, gets HTTP 200, and measures its entire thinking-off arm on a thinking lane. Also [78](traps/tools/78-tool-choice-accepted-and-ignored.md), where `tool_choice` is inert in both directions and therefore **fails open** on the standard way an agent framework gates a turn. Two further findings landed inside existing entries: a third reasoning field name split by route ([01](traps/reasoning/01-reasoning-field-two-names.md)) and the injection mirror of the in-text toggle ([66](traps/template/66-in-text-thinking-toggle-mutates-user-text.md#the-mirror-case-injection-on-ollama)). The same pass settled R2-39 on the stack it was scoped to, and established that SGLang is [not infeasible](mining/2026-07-28-sglang-on-gb10-feasibility.md) on this hardware class.
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

# Changelog

New entries and structural changes, newest first. Cadence: entries land as
they are verified; issue reports get a first maintainer response within a
few days.

## 2026-07-28

- **Traps [82](traps/template/82-system-prompt-relocates-to-last-user-turn.md) through [88](traps/runtime/88-cache-prompt-false-does-isolate-here.md): a fourth serving stack.** llama.cpp `b9878-2da668617` with `--jinja`, against a Mistral-family Q8_0 GGUF of **unstated provenance** supplied by **Exile** for coverage and doctor portability. The checkpoint is deliberately not characterised: no capability claims, no benchmarks, no refusal or alignment probing, and every finding is scoped either to that artifact or, where the mechanism is server-side, to the llama.cpp build. Five template traps, one server introspection trap, and one negative. The one to read is [84](traps/template/84-tool-roundtrip-then-user-turn-is-unrenderable.md): a completed tool round trip followed by a user turn cannot be rendered at all, and the HTTP 400 blames the template rather than the message list, so the operator debugs the wrong thing. [83](traps/template/83-template-carries-a-baked-default-system-prompt.md) is the one with the widest blast radius: a hard-coded default system prompt is injected whenever the request omits one, which means every no-system-prompt control arm ever run on this checkpoint was not a control.

- **Trap [88](traps/runtime/88-cache-prompt-false-does-isolate-here.md) is a negative, recorded with the same care as a positive.** `cache_prompt: false` **does** isolate a request from prior slot state on this build, which is a third data point that does **not** reproduce two prior stacks. It lands at measured here, raw not published, and with its build qualifier attached, because the whole value of a negative is the conditions under which it was obtained.

- **Traps 89 and 90, from [@drowzeys](https://github.com/drowzeys) (Keys)**, shared from his public notes rather than submitted, and credited by handle at his agreement. [89](traps/evaluation/89-hardlink-shard-pollution-invalidates-a-ladder.md): an in-place weight edit mutates the "stock" copy through a shared inode, so a quantisation ladder is measured against a baseline that moved. [90](traps/versioning/90-kernel-library-ships-cubins-for-one-arch-only.md): a kernel library ships cubins for one architecture only, and the six errors on the way there each look like a fixable config bug; **its check cannot be run on our hardware and stays inline, marked unverified, rather than going under `checks/` where the contract would imply we had exercised it.** Two more of his findings landed inside traps 62 and 79 rather than taking numbers.

- **Trap [33](traps/routing/33-moe-inference-topk-expansion-tax.md) promoted to reported by others + reproduced here**, on a quantised build. The finder's numbers are all bf16 under HF transformers; ours are NVFP4 on vLLM, which under our own different-quant-different-unit rule left the question open rather than settled. It survives at roughly the reported magnitude: monotone across k in {8, 16, 24, 32}, two scoring protocols, two independent passes each, with the pre-registered primary contrast at **-4.50 points** paired at n=600, discordant 37/10, exact McNemar **p = 9.8e-05**, and an independent replicate at -4.00 points, 37/13, p = 0.000936. The same run re-measured our own noise: all four same-k restart pairs landed inside the plus-or-minus 1.3 point band (largest 0.83), every raised-k contrast outside it. The choice-logprob arms, which are the finder's own protocol, came back at -3.17 and -3.67 against his reported -3.66. Every published figure was re-derived from the answer sheets before publication by a checker written separately from the analyser that produced them. Raw is **not** shipped: [MAINTAINING](MAINTAINING.md#shipping-raw-data-in-the-repo) reserves in-repo raw for calibration constants other entries cite, and applying that rule to our own result rather than making an exception for it is the point. The runnable scripts do ship. [Writeup](mining/2026-07-28-trap-33-q1-nvfp4-confirmed.md). **Second first-party confirmation of an external contributor's finding** in this registry, after trap [35](traps/evaluation/35-identical-weights-do-not-score-identically.md); the **Found by** line did not move in either case.

- **Traps 75 to 81: first Ollama coverage**, plus two findings that are not Ollama. Ollama was named in CONTRIBUTING as a stack with no entries at all and is now off that list. The one with the highest operator cost is [77](traps/reasoning/77-only-one-request-field-is-validated.md): exactly one request field is validated and every other one is accepted and dropped, so a harness ported from another server measures its whole thinking-off arm on a thinking lane and every request returns 200. [78](traps/tools/78-tool-choice-accepted-and-ignored.md) is the one to check today if you run agents: `tool_choice` is inert in both directions, so the standard way to gate a turn **fails open**. Entries: [75](traps/versioning/75-release-asset-renamed-pinned-url-404.md), [76](traps/runtime/76-device-rejection-log-line-is-not-fatal.md), [77](traps/reasoning/77-only-one-request-field-is-validated.md), [78](traps/tools/78-tool-choice-accepted-and-ignored.md), [79](traps/memory/79-out-of-range-context-request-accepted.md), [80](traps/runtime/80-reasoning-parser-batches-sse-deltas.md) (a reasoning parser batching the SSE stream, which cost us a published speculative-decoding figure that reversed sign from +12.6% to -32.2% when re-measured), and [81](traps/memory/81-stopped-container-has-not-released-memory.md).

- **Two Ollama findings landed inside existing entries**: a third reasoning field name, split by route, with `reasoning_content` on none of them ([01](traps/reasoning/01-reasoning-field-two-names.md)); and the injection mirror of the in-text thinking toggle, where the template appends the marker to the user's last message and it leaks into the scored answer ([66](traps/template/66-in-text-thinking-toggle-mutates-user-text.md#the-mirror-case-injection-on-ollama)).

- **R2-39 settled on the stack it was scoped to.** Refuted as stated: empty content tracks tools alone, in both thinking states, and every empty response carried a tool call. Not a defect, a harness reading `content` and ignoring `tool_calls`. Also recorded: SGLang is [not infeasible](mining/2026-07-28-sglang-on-gb10-feasibility.md) on aarch64 GB10 CUDA 13, which is the opposite of the expected result and is why the note exists.

- **Traps 63 to 74: the NVIDIA Nemotron 3 family**, three checkpoints on GB10-class nodes across vLLM 0.20.0 and 0.25.1, including this registry's first multimodal lane. The one to read is [63](traps/reasoning/63-reasoning-round-trip-one-correct-shape.md): the history-preservation gate on this family is called `truncate_history_thinking` and **`true` means discard**, which is the opposite polarity to the `preserve_thinking` this registry already documents, so a pipeline standardised on the known name silently does nothing. The field name compounds it: the template source reads `reasoning_content`, but the server drops that key before rendering and maps its own `reasoning` instead, so reading the template produces the wrong fix with high confidence. Entries: [63](traps/reasoning/63-reasoning-round-trip-one-correct-shape.md), [64](traps/reasoning/64-answer-lands-in-reasoning-on-toggle-conflict.md), [65](traps/reasoning/65-parser-only-rescue-kwarg.md), [66](traps/template/66-in-text-thinking-toggle-mutates-user-text.md), [67](traps/template/67-history-rendered-as-object-repr.md), [68](traps/template/68-multimodal-part-order-discarded.md), [69](traps/template/69-minor-template-defects.md), [70](traps/runtime/70-in-repo-parser-not-bundled.md), [71](traps/runtime/71-mtp-config-key-and-draft-count.md), [72](traps/runtime/72-media-fetch-errors-are-5xx.md), [73](traps/evaluation/73-multimodal-token-cost-not-attributable.md), [74](traps/evaluation/74-non-speech-audio-fabricated-captions.md).

- **Eight more Nemotron findings landed inside existing entries rather than as new numbers**, which is the deduplication outcome CONTRIBUTING describes and the one that keeps the registry from fragmenting: a measured empty-content floor plus the demonstration that no single floor is safe to copy ([12](traps/evaluation/12-empty-content-at-token-ceiling.md), pointer in [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md)), two quant-label instances failing in opposite directions plus the labelling pattern itself ([10](traps/quantization/10-quant-label-is-not-the-kernel-path.md)), host-side rather than CUDA memory pressure ([13](traps/memory/13-utilization-fraction-on-unified-memory.md)), an inverted generation-config instance ([21](traps/versioning/21-no-generation-config-server-defaults-win.md)), a family whose card-versus-config answer differs per member ([17](traps/evaluation/17-per-arm-recommended-sampling-confound.md)), the parser-less default ([02](traps/template/02-orphaned-think-close-tag.md)), three read-but-undocumented kwargs against one documented ([07](traps/reasoning/07-reasoning-effort-silently-ignored.md)), and a third route to an empty `content` ([23](traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md)).

- **R2-29 unblocked and settled**: tool calls as raw text on Nemotron NVFP4 is [refuted as worded and reframed](mining/2026-07-28-r2-29-tool-calls-refuted-as-worded.md). The leaked format is nested XML, not JSON, and on vLLM a tools request without the parser flags is rejected with HTTP 400 rather than degraded, so the plain claim is unreachable there.

- **Traps 56 to 62: first coverage of a DeepSeek-V4-Flash serving path**, measured at request level only against a live two-node lane on 2026-07-28. Statuses are split rather than uniform, because the evidence is: the four structural findings are **reproduced here** and name the public source file a stranger reads to check them, while the two behavioural ones (the cold-versus-cached divergence, the depth curve) are **measured here, raw not published** and say so. Entries: [56](traps/template/56-checkpoint-ships-no-chat-template.md), [57](traps/reasoning/57-thinking-kwarg-truthiness-coercion.md), [58](traps/reasoning/58-reasoning-effort-injects-hidden-preamble.md), [59](traps/reasoning/59-reasoning-roundtrip-confabulation.md), [60](traps/runtime/60-cold-prefill-and-cache-hit-disagree.md), [61](traps/evaluation/61-advertised-window-fails-silently.md), [62](traps/runtime/62-spec-decode-garble-under-wrong-drafter-config.md), plus a [model page](models/deepseek-v4-flash.md) and a pre-registered but [unrun experiment](mining/2026-07-28-chunked-prefill-vs-cache-replay-experiment.md). Entry 61 was **renamed at merge**: it collided on a title with trap 55 from the external block, the two are distinct material, and ours was the one renamed because the framing was the contributor's first. They cross-link.

- **Traps 43 to 55: the registry's first large external contribution**, from [@TheTom](https://github.com/TheTom), who maintains the offlabel operator guide. Thirteen entries land at **contributor-measured, conditions as reported**: he measured every one on his own hardware and stated the conditions, and we have not reproduced them here. He originally marked them "reproduced here", which was **our documentation bug rather than his error**: CONTRIBUTING then defined that label as "you ran it and can link or produce the raw", which he satisfied exactly. The [status vocabulary](CONTRIBUTING.md#status-vocabulary) now says what we meant by it. Of the fifteen in his PR, one more is **folded rather than held**: his 44 lands as an amendment inside traps [12](traps/evaluation/12-empty-content-at-token-ceiling.md) and [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md), at his own suggestion and credited in both, supplying the reason a budget floor has to be a distribution rather than a number. Exactly **one entry is held**, his 56, pending the with-and-without chunked-prefill pair its status promises and never states. His eight check scripts are in separate review against the check contract, so the entries land with their inline assertions intact and their `Runnable:` pointers removed; every stripped line is recorded verbatim and goes back unchanged when the scripts land. **Numbering is provisional and was assigned at merge**, because five staged sets competed for the same range. His block kept its internal ordering and its **base**, so 43 is still 43. It did **not** keep its numbers: one entry folded and one was held, so everything above 43 slid down one place against the numbers published in the PR, and twelve entries moved. This line originally claimed no entry of his moved, which was wrong; the [PR-to-main map](MAINTAINING.md#the-pr-to-main-number-map) is published so a bookmarked number can be resolved. See [MAINTAINING.md](MAINTAINING.md#numbering-in-this-merge). Entries: [43](traps/template/43-tool-args-string-not-mapping.md), [44](traps/quantization/44-fp4-dequant-scale-swizzle-layout.md), [45](traps/quantization/45-fa-all-quants-cpu-fallback.md), [46](traps/versioning/46-stale-build-missing-arch-kernel.md), [47](traps/runtime/47-prefix-caching-autodisabled-hybrid.md), [48](traps/routing/48-dual-stack-mdns-latency-tax.md), [49](traps/evaluation/49-prompt-not-tokenized-to-target.md), [50](traps/evaluation/50-hidden-state-dump-convention.md), [51](traps/quantization/51-single-backend-nan-fused-path.md), [52](traps/evaluation/52-speed-measured-on-a-broken-config.md), [53](traps/runtime/53-config-edit-never-took-effect.md), [54](traps/evaluation/54-run-order-and-warm-cache-artifacts.md), [55](traps/evaluation/55-supported-context-is-not-trained-context.md).

- [minefield-doctor](doctor/) hardened after two independent adversarial
  audits both ranked it their second finding: the tool could report CHECKED
  AND CLEAN for conditions it had not verified, against its own documented
  contract that anything uncheckable goes to COULD NOT CHECK. Every `ok()`
  call was audited. **Eight false-clean classes were converted**, six of them
  found during the audit rather than named in it: bogus-kwarg acceptance with
  no readable template; a non-200 kwarg probe credited as server strictness
  with no no-kwarg control; a rejection that came from `reasoning_effort`
  rather than from unknown-kwarg strictness; thinking-on returning no
  reasoning field and no think tags; a thinking toggle map in which no arm
  fires; an orphan-tag check reported clean across arms that never returned;
  empty content that did **not** hit the cap; and sampling defaults called
  "matching" a shipped `generation_config` when the two sides declared no keys
  in common. A fourth output bucket, **INCONCLUSIVE**, now separates "the
  probe ran but several materially different states produce this result" from
  "the probe could not run", matching the `UNKNOWN` level
  [checks/preflight_template.py](checks/preflight_template.py) already uses.
- Doctor: `--hf-revision`. `--hf-repo` always read `resolve/main`, so an
  operator serving a pinned revision was compared against today's mutable main
  and told they had drift. The revision is now resolved through the hub API to
  an immutable commit sha, that sha is printed in every config finding, and an
  unresolvable ref is reported as INCONCLUSIVE rather than silently used.
- Doctor: the tool probe no longer over-diagnoses. It forces a call with
  `tool_choice` where the server supports it, which separates
  `MODEL_ELECTS_NOT_TO_CALL` and `TOOL_CALLING_UNAVAILABLE` from
  `TOOL_MARKUP_NOT_PARSED`. Where `tool_choice` is unsupported the ambiguity
  cannot be removed, so the verdict is INCONCLUSIVE, printed with
  **CONFIDENCE: LOW** and all six candidate states listed, instead of the
  PROBLEM the old code asserted.
- Doctor: honest coverage. The root README's "checks most of this registry"
  is corrected to **17 of 42**, and every run now prints
  `implemented N/42 | executed on this stack N | clean N | problems N |
  inconclusive N | not implemented N` plus the caveats that make even 17 an
  overstatement: 25 shares trap 04's heuristic, 16 and 22 are annotations on
  the trap-12 finding, 10/17/21 need `--hf-repo`, and 04/20/25 need a render
  path.
- Doctor: committed regression suite. `doctor/tests/fixture_server.py` is a
  declared-behaviour fixture lane plus a fixture hub;
  `doctor/tests/test_doctor_verdicts.py` asserts the verdict for every
  scenario, pairs each defect with a control lane that differs only in the
  flag under test, and enforces two structural invariants: a CLEAN cannot be
  emitted without at least one assertion that held, and a not-clean verdict
  cannot be emitted without at least one that failed. `--json` now carries
  those assertions verbatim, not only prose. 31 tests, plus the two existing
  suites, all stdlib-only and contacting no network.
- Doctor and [checks/preflight_template.py](checks/preflight_template.py):
  landed the previously staged fixes. vLLM render path
  (`/v1/chat/completions/render` plus `/detokenize`, falling back to
  `/tokenize`), so traps 04, 20 and 25 are no longer skipped on every vLLM
  lane; multimodal probes (surface, usage attribution, content-part ordering,
  media error classification, with audio and video declared uncovered);
  quantisation read from `hf_quant_config.json` when `config.json` is silent,
  so a ModelOpt NVFP4 checkpoint is no longer reported as unquantized; and
  four kwarg-enumeration false-positive classes removed (Jinja tests, filters,
  macro parameters, namespace keyword arguments) while the self-defaulting
  idiom that had been suppressing real kwargs is recovered.
- Trap [35](traps/evaluation/35-identical-weights-do-not-score-identically.md)
  promoted from **reported by others** to **reproduced here**, and generalised.
  [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b) remains the
  originating report (98.7% cross-machine agreement, bf16 under HF
  transformers). First-party measurement on a different build class,
  Qwen3.6-35B-A3B NVFP4 under vLLM nightly `a346d589` on two GB10 nodes:
  pooled 3513/3600 = **97.58%** item agreement across six pairings of four
  identical-configuration runs, MMLU n=600 greedy. The generalisation is that
  **two machines are not required**: the cross-machine pairs (97.17%, 97.83%,
  98.33%) straddle the within-process pair (97.33%), so the disagreement lives
  inside a single server process and same-machine serial execution does not buy
  determinism. Speculative decoding ruled out as the cause (97.33% to 98.17%
  with overlapping intervals). Raw, serial scorer and an independent
  re-derivation script published in
  [mining/2026-07-28-agreement-floor-data/](mining/2026-07-28-agreement-floor-data/);
  write-up in
  [mining/](mining/2026-07-28-our-agreement-floor-greedy-not-reproducible.md).
  Calibration adopted: an MMLU-style paired delta below about **1.3 points at
  n=600** is not distinguishable from a re-run on that stack. The band is an
  accuracy delta over four-way multiple-choice items and does **not** transfer
  to binary-outcome results such as firing-rate counts.
- Trap
  [42](traps/evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md):
  a single-turn eval harness scores tool-call exits as wrong answers.
  Found by [@apollo-mg](https://github.com/TheTom/offlabel/pull/10#issuecomment-5093534067)
  and measured at n=492 on Laguna S 2.1 UD-Q2_K_XL under llama.cpp on 4x
  Tesla P100: pooled pass@1 71.95% against his own 90.85% baseline, a drop
  of 18.90 points, with WRONG moving 30 to 31 and accuracy conditional on
  attempting at 354/386 = 91.71%. Lands as **reported by others** with
  **raw published** (12.7 KB tarball: verbatim system prompt, tool schemas,
  per-sample buckets and token counts for all 164x3, run and driver logs).
  The depth-side half of the same exit-path mechanism was measured here
  independently on NVFP4 under vLLM 0.25.1 on GB10.
- The trap carries an explicit open question rather than a settled claim:
  the termination benefit (no-extractable 11 to 0, cap-hits 12 to 1) is
  untested with tool output fed back, and both parties recorded opposing
  predictions before the discriminating arm runs. Cite it as measured
  under schema-presence-only.
- Nine traps ([33](traps/routing/33-moe-inference-topk-expansion-tax.md)
  through
  [41](traps/runtime/41-static-batching-buys-power-not-throughput.md))
  mined from [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)'s
  public research log on raising a pretrained MoE's inference top-k from 8
  to 32, offered by him for this purpose and credited by handle. All nine
  land as **reported by others**; three of them were re-scored here from the
  per-item JSON he publishes, and the recomputations match his stated
  p-values.
- New category [traps/routing/](traps/routing/) for MoE expert routing and
  activation config. Trap 33 did not fit quantization (nothing is
  quantized) or runtime (it is a model-config knob, not a stack property),
  and filing it under either would have hidden it from the people who need
  it. As MoE serving knobs proliferate, this is where they go.
- Trap [33](traps/routing/33-moe-inference-topk-expansion-tax.md) is the
  headline: raising a MoE's active-expert count costs accuracy **before any
  training**, with no error and no warning, because the selected gate scores
  are renormalized and the extra experts dilute rather than add. Selection
  is intact and the nesting is exact. Measured monotone in k on two
  benchmarks (MMLU 84.33 to 80.67, GSM8K 89.33 to 86.50, k=8 to k=32,
  n=600 paired, both significant), and repaid with zero training by scaling
  the tail ranks back down.
- The other eight are measurement traps that made real numbers wrong:
  [34](traps/evaluation/34-baseline-you-degraded-yourself.md) a baseline you
  degraded yourself (same arm, same items: a significant +6.10 pt win
  against the handicapped reference, no effect against the shipped one),
  [35](traps/evaluation/35-identical-weights-do-not-score-identically.md)
  identical weights agreeing on only 98.7% of items across machines,
  [36](traps/evaluation/36-token-cap-is-an-arm-level-handicap.md) token caps
  binding at 33.4% of items for one arm and 0.0% for another,
  [37](traps/evaluation/37-uniform-zero-is-a-harness-verdict.md) three
  distinct all-arms-zero results that were all harness faults, one of them
  reporting `infra_error_n=0`,
  [38](traps/template/38-template-owns-the-opening-think-tag.md) the opening
  think tag that the template supplies and the model never writes,
  [39](traps/runtime/39-device-map-auto-offloads-and-returns-garbage.md)
  `device_map="auto"` spilling onto an excluded device and returning
  gibberish,
  [40](traps/evaluation/40-ngram-decontamination-false-positives.md) a
  contamination screen removing 31.7% of a corpus on the strength of one
  boilerplate n-gram, and
  [41](traps/runtime/41-static-batching-buys-power-not-throughput.md) static
  batching that raised GPU utilization to 100% and throughput not at all.
- Verification queue recorded in
  [mining/](mining/2026-07-28-qwen36-a6b-verification-queue.md): trap 33 is
  the first candidate for a **reproduced here** upgrade, since we have a
  Qwen 3.6 35B-A3B NVFP4 lane and his measurements are all bf16 on HF
  transformers.

## 2026-07-27

- [Doctor](doctor/) portability notes from its first mlx_lm field run: 6 of
  9 check families port cleanly with no misfires; the two gaps (stack
  identification, and history-assembly checks lacking a render path on
  stacks without a template endpoint) degrade to explicit COULD NOT CHECK
  rather than wrong output. A `--template-file` argument is recorded as a
  tracked enhancement so the history-assembly checks can run from the
  `chat_template.jinja` that ships next to local weights.
- Trap [32](traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md)
  landed, reproduced here: mlx_lm's server `--max-tokens` launch flag is a
  per-request default, not a ceiling. A client sending a larger
  `max_tokens` runs straight past it (measured 1600 through a 1024 flag,
  167 s on a lane whose normal replies take 1 to 2 s), with no warning and
  nothing in the response distinguishing clamped from obeyed. Behavioral on
  mlx-lm 0.31.3; source-confirmed at that release and current main, where
  the flag's own help text calls it a default. Combined with trap
  [29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md) on
  the same stack, mlx_lm has no server-side gate a client cannot exceed by
  asking.
- MLX coverage becomes real: a read-only characterization pass on a stock
  mlx_lm lane (prism-ml Ternary-Bonsai-27B-mlx-2bit, Apple silicon) lands
  MLX-scoped sections in five entries. Trap
  [01](traps/reasoning/01-reasoning-field-two-names.md): `reasoning` is the
  one live field name on mlx_lm (non-streaming and streaming), plus two MLX
  wrinkles: empty channels are ABSENT keys (a thinking cap-hit has no
  `content` key at all, so `msg["content"]` raises KeyError), and every
  streaming delta carries `role="assistant"`. Traps
  [03](traps/reasoning/03-enable-thinking-default-drift.md) and
  [29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md):
  `--chat-template-args` is mlx_lm's spelling of the
  server-supplies-the-kwarg arm, and it is a per-request default, not a
  gate (second stack for 29). Trap
  [07](traps/reasoning/07-reasoning-effort-silently-ignored.md): third
  stack, with a wider acceptance surface: even invented TOP-LEVEL body keys
  return 200, so a typoed parameter is a silent behavior change. Trap
  [12](traps/evaluation/12-empty-content-at-token-ceiling.md): reproduced,
  with the absent-key flavor of the signature. Traps
  [20](traps/reasoning/20-reasoning-write-field-name-diverges.md) and
  [04](traps/template/04-history-reasoning-stripping.md): the server emits
  `reasoning` while the shipped template only reads back
  `reasoning_content`, confirmed behaviorally with a marker round-trip;
  naive replay silently strips all prior reasoning on this lane. Per-model
  and per-stack index rows added for mlx_lm.
- New [mining/](mining/) area: verification notes on mined candidates that
  did not (or could not) promote to entries, so negatives and blocked tests
  are recorded instead of lost. First three notes, from a hardware
  verification pass over the round-2 queue: R2-39 (thinking plus tools
  yields empty output, Ollama-reported) did not reproduce on vLLM across a
  2x2 kwarg-by-tools matrix on two lanes, scoping the candidate to Ollama;
  R2-31 (DeepSeek V4 system-message quality cliff) did not reproduce at
  small n on the production lane, with an identical system-independent miss
  in all three arms; and R2-27/R2-23/R2-10/R2-29 are recorded as not
  testable on current lanes with exactly what each test needs.
- Trap [06](traps/reasoning/06-identity-sentence-eviction.md) status
  resolved: the promised independent test on a second stack is in, and the
  prefix-key mechanism did not reproduce there (identity as literal first
  line fired 0/40 at the critical cell). A position-generic tail effect was
  found instead: roughly 29 tokens of any token-band-matched text appended
  at the END of the system prompt reopens the gate on both tested builds
  (hybrid and NVFP4, in-run interleaved controls, every suffix vs bare
  p <= 0.025; identity vs matched fillers NS). Entry now scopes both
  results by stack, and the check and fix cover both ends of the prompt.
  Full data and drivers: laguna-s21-lab `identity-prefix/`.
- Trap [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md)
  gains the production-lane replication (28-row ceiling audit, three
  lanes, n=2 to 3 per cell): the budget floor is a distribution, not a
  number. The 27B produced 26K to 61K reasoning chars on the identical
  prompt, so even a 16384 ceiling fails 1 in 3; every capped tail was
  honest truncation, not degeneration. A no-thinking control completes
  everywhere in 1.5K to 5K tokens, tying the floor to
  [trap 29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md)'s
  client-kwarg re-enable path.
- Trap [31](traps/evaluation/31-leftover-oracle-reranker.md) landed,
  reproduced here on one frozen suite: a leftover oracle re-ranker (a
  temp-directory debugging script that boosts candidates by expected id,
  or looks them up by the answer's file name stem) turns a failing
  retrieval eval into a passing one, and the inflated number outlives the
  script. Arms were reconstructed mechanisms run in one labelled harness
  next to the honest engine, not recovered original code. Ships the two
  detection fingerprints (top-1 equals top-3 exactly for expected-id
  boosting; saturation at exactly 1.0 for answer-derived lookups) and a
  copyable no-oracle negative control that fails the run when injected
  answer metadata changes a ranking.
- Trap [30](traps/template/30-default-system-message-silently-replaced.md)
  landed, reproduced here (structural, read from the shipped chat template
  of the serving checkpoint pair): the template's built-in default system
  message is used only when the caller sends no system message at all, and
  any caller system message replaces it wholesale. Consequences: every
  with-system-prompt condition is confounded with default-identity-absent
  by construction, and "no system message", "empty system message", and
  "any system message" are three distinct rendered prompts. Found while
  designing the identity-prefix study, before any cell ran.
- Cross-family measurements spliced into three existing entries (staged by
  the standardized probe sweep, landed after review): trap
  [04](traps/template/04-history-reasoning-stripping.md) gains the Qwen 3.6
  template confirmation (same stripping machinery, different rendering, no
  behavioral collapse) and the version-dependent-fix warning (Qwen 3.5
  reads no `preserve_thinking`); trap
  [07](traps/reasoning/07-reasoning-effort-silently-ignored.md) upgraded to
  reproduced-here on two Qwen models on llama.cpp, plus the
  bogus-kwarg-accepted-with-200 finding; trap
  [03](traps/reasoning/03-enable-thinking-default-drift.md) gains the
  four-lane absent-kwarg landing map.
- [minefield-doctor](doctor/) shipped: a single stdlib-only file that
  diagnoses any OpenAI-compatible endpoint against the registry.
  Read-only and bounded (at most 8 small temperature-0 completions),
  three-section output (PROBLEMS / CHECKED AND CLEAN / COULD NOT CHECK),
  every finding linked to its trap, and a `--report` flag that emits a
  paste-ready "I hit a trap" block. Acceptance-tested on five lanes
  across llama.cpp, vLLM, and MLX, where it independently rediscovered
  traps 21, 29, 07, and the 22-class cap behavior already measured there.
- Trap [29](traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md)
  landed, reproduced here: a server-side reasoning-off flag is a default,
  not a gate; any client kwarg re-enables thinking and blows non-thinking
  token budgets (15K to 61K chars of reasoning measured through an 8192
  cap).
- Verification round on our fleet: traps
  [26](traps/tools/26-tool-call-inside-unclosed-think.md) and
  [24](traps/template/24-official-template-breaks-cpp-jinja.md) gain dated
  not-reproduced-on-current-build notes (30/30 forced-tool turns clean with
  thinking engaged on llama.cpp b9066/b9193; full tool schema rendered by
  the C++ engine despite `|items` in the template), and the per-model index
  gains a clean-preflights table starting with Ternary-Bonsai-27B on MLX.
  Negative results are recorded, not dropped.
- Traps [21](traps/versioning/21-no-generation-config-server-defaults-win.md)
  and [22](traps/evaluation/22-family-card-budget-floors-differ-by-size.md),
  reproduced here on our llama.cpp lanes: no generation_config.json means
  the server's built-in sampling silently becomes "the model's settings"
  (five parameters diverged from the card on Qwen3.5-9B, matched exactly on
  the Qwen3.6-27B control), and the thinking budget floor differs by size
  within one family (9B converts at 8192, 27B needs 16384 on the same
  byte-identical task).
- Six new reported-by-others traps mined from upstream trackers and
  community template work, every linked source read and verified before
  writing (two candidates were dropped when their GitHub issues turned out
  to be resolved as user error):
  [23](traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md)
  streaming answer in the reasoning channel,
  [24](traps/template/24-official-template-breaks-cpp-jinja.md) official
  templates break C++ Jinja engines,
  [25](traps/template/25-empty-think-blocks-poison-prefix-cache.md) empty
  think blocks poison prefix cache,
  [26](traps/tools/26-tool-call-inside-unclosed-think.md) tool call inside
  unclosed think,
  [27](traps/quantization/27-nvfp4-accuracy-cliff-config-misses.md) NVFP4
  accuracy cliffs from config misses,
  [28](traps/runtime/28-mtp-fails-only-under-concurrency-or-temperature.md)
  MTP fails only under concurrency or temperature. Trap 19 gains the
  vLLM parser-pair face. Hall of fame gains an upstream-reports table.
- New trap [20](traps/reasoning/20-reasoning-write-field-name-diverges.md):
  the reasoning write field is runtime-specific. Found by @Defilan while
  replicating trap 04 on llama.cpp: only `reasoning_content` reaches the
  llama.cpp template, `reasoning` is silently dropped and renders
  byte-identical to the stripped arm, while vLLM passes `reasoning` through.
  Trap 04's fix section now names the correct field per runtime, and its
  stacks section carries the llama.cpp rendering replication.
- Contribution overhaul: "I hit a trap" issue form (four plain questions,
  maintainer writes the entry), [MAINTAINING.md](MAINTAINING.md) promotion
  workflow and status conventions, per-model index at
  [models/README.md](models/README.md), finder named at the top of every
  entry, README reframed around the reader who just lost an evening.
- Expanded beyond the founding stacks: twelve new traps (08 through 19)
  covering runtime toolchains, container images, quantization kernel paths,
  unified memory, speculative decoding, eval harnesses, versioning, and
  tool calling. Category directories, per-entry statuses,
  [HALL_OF_FAME.md](HALL_OF_FAME.md).
- Date normalization: found-dates re-anchored to shipping commits.
- Launched with seven traps (reasoning fields, templates, thinking control,
  scorer normalization) and `checks/preflight_template.py`.

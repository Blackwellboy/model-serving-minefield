# Changelog

New entries and structural changes, newest first. Cadence: entries land as
they are verified; issue reports get a first maintainer response within a
few days.

## 2026-07-28

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

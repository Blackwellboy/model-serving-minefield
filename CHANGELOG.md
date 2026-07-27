# Changelog

New entries and structural changes, newest first. Cadence: entries land as
they are verified; issue reports get a first maintainer response within a
few days.

## 2026-07-27

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

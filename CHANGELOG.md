# Changelog

New entries and structural changes, newest first. Cadence: entries land as
they are verified; issue reports get a first maintainer response within a
few days.

## 2026-07-27

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

# Trap 25: empty historical think blocks poison the prefix cache

**Found by @latent-variable.**

**Status: reported by others** (upstream Qwen template issue with the
minimal fix in the report, closed with the fix carried into later Qwen3.6
template releases); not independently reproduced here.

**Symptom.** Multi-turn and agent sessions burn more prefill than they
should: prefix-cache hit rates sag, equivalent conversation histories
tokenize differently between requests, and the assembled prompt
accumulates junk `<think></think>` pairs on assistant turns that never
carried any reasoning text. Nothing errors. You pay for it in cache
misses, token counts, and length-sensitive measurements that drift with
history shape.

**Mechanism.** The chat template emits the `<think>...</think>` wrapper
for historical assistant turns even when `reasoning_content` is empty, so
the serialized prompt changes without adding information. Two histories
that are semantically identical render differently depending on which
turns happened to carry an empty reasoning field, which defeats prefix
reuse and inflates every prompt-length number
([QwenLM/Qwen3.6 #131](https://github.com/QwenLM/Qwen3.6/issues/131),
which includes the minimal template fix).

Note the relationship to [trap 04](04-history-reasoning-stripping.md):
these are the two directions of the same rendering surface. Trap 04 is
real reasoning missing from the render; this is empty wrappers present in
the render. A lane can have both at once, and both are invisible to
request-shaped checks.

**Stacks and builds bitten.** Qwen 3.6 with the affected template
revisions (upstream issue, 29 comments; closed as fixed in later Qwen3.6
releases). Template-revision-scoped: whether your lane has it depends on
which template file your checkpoint or server actually loads, which is
trap 03's territory.

**The check.** Render a three-turn conversation where the prior assistant
turns carry content but no reasoning, and grep the assembled prompt for
empty think pairs. Then token-count two equivalent histories that differ
only in empty-reasoning turns. Confirmed if empty wrappers appear or the
counts differ.

**The fix.** Use a template revision that skips the wrapper when the
reasoning field is empty (the upstream fix), or strip empty blocks in
your history assembly. Pin and record the template revision next to any
cache-hit-rate or prompt-length number.

**Found.** 2026-07-27 (mined from upstream).

**Attribution.** @latent-variable
([QwenLM/Qwen3.6 #131](https://github.com/QwenLM/Qwen3.6/issues/131),
report and minimal fix). Related entries:
[trap 04](04-history-reasoning-stripping.md),
[trap 03](../reasoning/03-enable-thinking-default-drift.md) (template
revision drift decides which behavior you get).

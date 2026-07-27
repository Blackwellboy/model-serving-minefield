# Trap 22: a family card is not a model card, the thinking budget floor differs by size

**Found by Blackwellboy.**

**Status: reproduced here** (byte-identical task across two sizes of one family on one stack, one sample per cell, plus a published 40-sample map on a third family member on a second stack). Small n on the new cells; stated as such.

**Symptom.** You set the max_tokens ceiling that worked fine on one member
of a model family, run its sibling, and hard tasks come back as HTTP 200
with empty content (trap 12's signature). The family-level advice ("8K is
plenty for thinking models") was a model-level fact.

**Mechanism.** Thinking-token demand on the same task varies by multiples
between sizes of one family, so the budget that converts empties on one
size still starves another. Measured on a byte-identical six-requirement
coding task, thinking explicitly on, same prompt, same stack (llama.cpp),
one sample per cell:

| max_tokens | Qwen3.5-9B Q4_K_M | Qwen3.6-27B Q4_K_M |
|---|---|---|
| 512 | empty content at cap | empty content at cap |
| 4096 | empty content at cap (~15K chars reasoning) | empty content at cap |
| 8192 | **converts: finish=stop, full code** | empty content at cap (~30K chars reasoning) |
| 16384 | not run | **converts: finish=stop, full code, ~42K chars reasoning** |

The 27B's 16K-conversion tail is non-degenerate (unique-line ratio 0.81,
zlib ratio 0.34): honest long reasoning, truncation not loop, so budget was
genuinely the fix (contrast the degeneration signature in trap 16). The
published 40-sample map on Qwen 3.6 35B-A3B (vLLM, different task) converts
at 8192
([qwen-ceiling](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/qwen-ceiling)).
Three family members, three different safe floors on hard tasks:
approximately 8K, above 8K to 16K, and 8K, and nothing on any card says so.

**Stacks and builds bitten.** llama.cpp b9066 (Qwen3.5-9B Q4_K_M) and b9193
(Qwen3.6-27B Q4_K_M), single samples; vLLM/GB10 (Qwen3.6-35B-A3B NVFP4),
40-sample published map. Task difficulty obviously shifts the absolute
numbers; the per-size spread is the point.

**The check.** Before trusting any per-family budget guidance: run your
hardest routine task at your production ceiling on THE model you deploy,
thinking on, and check for empty content at cap. One request answers it.

**The fix.** Set ceilings per model, not per family, and re-measure on
every size or variant swap (trap 14's discipline applied to budgets).
When a cap-hit appears, apply trap 16's bucketing before concluding
anything.

**Found.** 2026-07-27, standardized probe sweep plus follow-up arms.

**Attribution.** Blackwellboy. Probe and follow-up JSONs in the sweep
results (`probe_*`, `hfollow_*`, `hdegen_*`).

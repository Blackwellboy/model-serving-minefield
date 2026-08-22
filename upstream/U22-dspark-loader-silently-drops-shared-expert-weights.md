# U22: a speculative drafter can silently skip weights and look like a model speed regression

**Reported by @tonyd2wild.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The loader mapping fix is in the source recipe's current main.

**Issue state: closed, fixed.** Patch 4 is documented as required for the affected 0731 DSpark runtime.

**Primary source.** [source commit 8a62e8b8](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/commit/8a62e8b8d04e5c65d4b4b9dc60134f5b3547f7c5), read on 2026-08-21, including `DSPARK-SHARED-EXPERT-FIX.md` and the README update.

**Registry relationship.** This upstream record overlaps the already-routed open canonical candidate **Q17 / Issue #38** (`[trap] A DSpark draft loader silently drops the shared expert`). It is corroborating/upstream evidence for that candidate, **not a second independent discovery and not a new canonical trap number**. Q17 remains deliberately unnumbered until a promotion PR is built from current `main` with its evidence split and CONFIRM/REFUTE gate preserved. See https://github.com/Blackwellboy/model-serving-minefield/issues/38 and `mining/OPEN_QUESTIONS.md`.

**Symptom.** Swapping to the official DeepSeek-V4-Flash-0731 checkpoint roughly halves speculative decode throughput while answer quality remains correct. Normal INFO-level startup logs report no obvious failed load, so the slowdown looks like a checkpoint regression or hardware/config problem.

The source measured, with the loader fix as the intended variable, draft acceptance moving from 25.7% to 60.2%, mean accepted tokens/step from 2.28 to 4.01, mean decode from 32.7 to 55.4 tok/s and peak from 42.0 to 66.1 tok/s. Decode steps/s stayed around 14, localizing the deficit to draft acceptance rather than target step time.

**Mechanism.** The affected DSpark draft loader renamed the shared expert's `w2` to `down_proj` but did not map `shared_experts.w1` and `shared_experts.w3` onto `shared_experts.gate_up_proj`. Those checkpoint tensors matched no draft parameter and fell through a `logger.debug("Skipping unknown DSpark weight")` path that is invisible at INFO. The source counts twelve dropped tensors across three draft stages. Because the target model still verifies speculative tokens, a degraded drafter can preserve output correctness while acceptance and speed collapse.

**What we have not done.** We have not independently loaded the affected checkpoint with and without the mapping fix. The source explicitly notes that the preview checkpoint carries the same tensor names but was not measured with Patch 4, so the size of the effect must not be generalized to every DeepSeek V4 artifact.

## If you have this stack

Pin the affected runtime/checkpoint. At load time, enumerate checkpoint tensors expected by the draft model and every skipped/unmatched parameter at INFO-or-louder instrumentation. Compare stock versus corrected mapping while holding target weights, k, KV dtype, prompts and warm state fixed. Record steps/s, drafted throughput, per-position acceptance and accepted tokens/step.

**CONFIRM.** The stock loader leaves the shared-expert `w1/w3` shards unmatched, the corrected mapping loads them, and acceptance/accepted-tokens-per-step recover while target-model output remains correct and decode steps/s stays approximately unchanged.

**REFUTE.** The allegedly affected build already loads all shared-expert tensors, or restoring the mapping does not change draft acceptance under a matched A/B.

## Attribution

Root-caused, measured and documented by @tonyd2wild in the source recipe. The registry has not independently reproduced it. This evidence should remain linked to Q17 / Issue #38 rather than being presented as a separate canonical discovery.

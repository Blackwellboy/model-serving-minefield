# U37: a long cold prefill can starve a peer decode without any preemption

**Reported by @Acermax.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer reproduced.** MiaAI-Lab reproduced the slowdown on its own 2x GB10 kit, identified the shared step-budget mechanism, shipped a scheduler policy and posted a live before/after retest.

**Issue state: closed, fixed.** MiaAI-Lab issue #6 was closed after commit `f3043c95bbf95fb91dd160fe58d740cd152a02c3` added the mixed-prefill decode-floor policy.

**Primary source.** [MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks issue #6](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/issues/6), its maintainer reproduction/fix comment, and [fix commit `f3043c9`](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/commit/f3043c95bbf95fb91dd160fe58d740cd152a02c3), read on 2026-08-30.

**Symptom.** On the published 2x DGX Spark GLM-5.3 EXL3 recipe, an already-decoding ~100K request fell from roughly 51-55 tok/s to 5 tok/s while a peer ~100K cold prefill shared the engine. Preemption stayed at zero and speculative acceptance stayed effectively perfect, so the usual preemption/drafter health signals looked green while interactive decode latency collapsed.

**Mechanism.** In the affected scheduler, `max_num_batched_tokens=1024` is the whole engine-step budget. A DFlash2 k=7 decode needs only a small slice of that budget, leaving roughly 1016 tokens for the peer sparse-MLA prefill chunk. That chunk has a large per-step cost, so decode still makes progress but only once per long mixed step. MiaAI-Lab's default fix became `GLM53_MIXED_PREFILL_CHUNK=skip`: when another running request is already decoding, do not schedule the peer prefill in that step; solo prefill remains 1024.

The maintainer's live retest after the fix reported an ~80K solo decode at 68.1 tok/s, the active decode while the peer cold-prefilled at 69.2 tok/s, and the peer's later decode at 68.2 tok/s. This is a scheduler fairness/step-budget result on the pinned recipe, not a claim that all chunked-prefill engines need serialization.

**What we have not done.** We have not independently reproduced this mixed sparse-MLA prefill/decode interaction on Blackwellboy infrastructure.

## If you have this stack

Run a paired test with unique cold prefixes: one long request decoding by itself, then the same decode workload while a second long cold prefill is admitted. Record per-lane streamed timestamps, running/waiting counts, preemptions, prefix-cache hits, speculative acceptance and the configured step budget. Then repeat with the recipe's mixed-prefill skip policy while holding model/runtime/sampling fixed.

**CONFIRM.** The affected arm shows a large decode-rate/inter-token-gap collapse only while the peer cold prefill occupies mixed steps, with zero preemptions and healthy acceptance, and the skip policy restores the decode floor while moving the cost into prefill waiting/TTFT.

**REFUTE.** Decode remains stable during the matched cold-prefill overlap on the affected revision, or the slowdown persists unchanged after the mixed-prefill policy is proven active.

## Attribution

Reported by @Acermax in issue #6; MiaAI-Lab reproduced the mechanism and shipped commit `f3043c9`. The registry has not independently reproduced the measurement.

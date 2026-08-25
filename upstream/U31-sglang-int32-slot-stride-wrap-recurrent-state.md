# U31: 32-bit slot-stride multiplication can wrap into another request's recurrent state

**Reported by @ch-wan.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #33974 is merged.

**Primary source.** [SGLang PR #33974](https://github.com/sgl-project/sglang/pull/33974), read on 2026-08-25.

**Symptom.** A clean boot can work at low slot ids and later show silent state divergence, fake speculative acceptance or an illegal access as slot ids grow. The load-dependent threshold makes cold or low-concurrency validation look healthy.

**Mechanism.** Unified-memory conv/SSM state views carry very large slot strides. Each stride can fit in int32 while `slot * stride` does not. The affected CuTe path folded the multiplication into 32-bit arithmetic, so sufficiently large slot ids wrapped into another slot's bytes or outside the allocation. The merged fix promotes slot ids before the stride multiplication.

**What we have not done.** We have not reproduced this high-slot-id SGLang kernel path on Blackwellboy infrastructure.

## If you have this stack

Pin the pre-fix build and replay the affected state kernel over increasing slot ids using faithful unified-memory strides, with an int64-addressing/static-layout control. Include low slots that should pass and slots above the reported wrap boundary.

**CONFIRM.** The pre-fix path is correct at low slot ids but diverges or faults at higher ids, while the int64/static control remains correct.

**REFUTE.** Pre-fix address arithmetic remains exact across the reported slot-id/stride range and matches the control.

## Attribution

Reported and fixed upstream by @ch-wan in SGLang PR #33974. This is separate from U30's recycled-page-tail mechanism. The registry has not independently reproduced the measurement.
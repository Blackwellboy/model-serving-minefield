# U30: recycled unified-memory page tails can leak historical bytes into speculative attention

**Reported by @ch-wan.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #33974 is merged.

**Primary source.** [SGLang PR #33974](https://github.com/sgl-project/sglang/pull/33974), read on 2026-08-25.

**Symptom.** Unified-memory + DSPARK speculative serving can show fake acceptance, invalid accuracy, NaNs or load-dependent corruption. Poisoning the pool makes the class deterministic; ordinary clean boots can hide it.

**Mechanism.** Recycled partial pages can expose historical bytes in unused tail rows. The affected MLA path reads whole page envelopes and masks rows beyond `seq_len` arithmetically, which is not NaN-safe. Speculative verification repeatedly lands on fresh tail pages and amplifies exposure. The merged fix zeroes page envelopes when the allocator hands them out.

**What we have not done.** We have not reproduced the affected unified-memory/DSPARK allocation path on Blackwellboy infrastructure.

## If you have this stack

Pin the pre-fix build, poison or otherwise mark page envelopes, recycle pages under unified memory with DSPARK, and compare with a zero-on-handout or static-pool control. Record acceptance and accuracy as well as NaNs/crashes.

**CONFIRM.** Recycled tail contents influence the pre-fix speculative/attention result or create fake acceptance, while zero-on-handout/static controls remain clean.

**REFUTE.** The pinned pre-fix kernel never consumes stale partial-page tail contents and poisoned vs clean/recycled controls remain equivalent.

## Attribution

Reported and fixed upstream by @ch-wan in SGLang PR #33974. This is one of two independent root causes in that PR; U31 records the separate slot-stride overflow. The registry has not independently reproduced the measurement.
# U36: prefix caching can be configured on while the reported hit path stays at zero

**Reported by @ThinkCode.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: none.** No maintainer confirmation is claimed from the source thread.

**Issue state: open.** The source issue remained open when re-read on 2026-09-13.

**Primary source.** [tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark issue #13](https://github.com/tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark/issues/13), read on 2026-09-13.

**Symptom.** The server reports `enable_prefix_caching=True`, repeated byte-identical prefixes are sent, and the prefix-cache query counter rises, but the reported hit counter stays at zero. The source reports more than 442,000 cache queries with zero hits on its lane.

The source also records a runtime warning that fine-grained prefix-cache hits are disabled because `KpoolTailManager` requires block-aligned lookups. The reporter then tested an exactly block-aligned 4,608-token prompt (2 × block size 2,304) twice and still observed zero new hits; a deliberately unaligned control also produced zero hits. Four concurrent byte-identical ~8k prefixes likewise produced zero hits.

**Mechanism boundary.** This entry does **not** claim that `KpoolTailManager` itself is defective or that prefix caching is universally broken on SM121. The public evidence establishes a narrower operational trap: configured/enabled state did not correspond to a usable hit path under the reported recipe and conditions. The reporter explicitly says fixability was not established.

**Reported conditions.** 2× NVIDIA GB10 / SM121, TP2, dual-rail RoCE, `RedHatAI/GLM-5.3-Flash-NVFP4`, DFlash2 k=7, block size 2304, FP8 KV, eager mode, recipe around upstream revision `7497e96` as described in the source issue.

**What we have not done.** We have not reproduced the zero-hit behavior on Blackwellboy infrastructure and have not independently localized the responsible component.

## If you have this stack

Record the exact runtime/image/model revision and cache configuration. Send the same long prefix twice while recording the prefix-cache query and hit counters before and after each request. Include one exactly block-aligned prefix and one deliberately unaligned control.

**CONFIRM.** Queries increase while hits remain zero for repeated byte-identical prefixes, including an exactly block-aligned control, under the affected pinned stack.

**REFUTE.** Repeated identical prefixes produce cache hits on the same pinned stack, or the reported zero-hit result is explained by a request/config difference that bypassed the cache entirely.

## Attribution

Reported and measured publicly by **@ThinkCode** in issue #13. The registry has not independently reproduced it.

# U28: a prefix-cache hit can restore another request's conv state under the prefill graph

**Reported by @ispobock.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #34184 is merged.

**Primary source.** [SGLang PR #34184](https://github.com/sgl-project/sglang/pull/34184), read on 2026-08-25.

**Symptom.** A hybrid-SWA/Mamba request can decode from a convolution checkpoint it never produced. The request may remain wrong for its whole generation. The failure requires the prefill CUDA graph, chunked prefill, concurrency and a prefix-cache hit; disabling the prefill graph removes it.

**Mechanism.** Captured prefill replay read stale `mamba_track_mask` and `mamba_track_indices` rows left by a previous replay. The current request's window could therefore be scattered into an earlier request's checkpoint, and a later prefix-cache restore loaded that wrong state. The merged fix clears those track rows with the other captured-tail buffers.

**What we have not done.** We have not reproduced the affected hybrid-SWA/Mamba graph/cache path on Blackwellboy infrastructure.

## If you have this stack

Pin the pre-fix build, enable the prefill CUDA graph and prefix cache, use chunked prefill with concurrent prompts, and compare cache-hit generations/logprobs and restored conv state with an eager or flushed-cache control.

**CONFIRM.** The pre-fix graph path writes or restores a checkpoint using stale track destinations and diverges from the flushed/eager control, while the fixed build does not.

**REFUTE.** The pinned pre-fix graph path is state- and output-equivalent to the flushed/eager control across the reported cache-hit/concurrency shape.

## Attribution

Reported and fixed upstream by @ispobock in SGLang PR #34184. The registry has not independently reproduced the measurement.
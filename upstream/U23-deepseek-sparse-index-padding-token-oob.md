# U23: invalid padding indices can drive a sparse-KV gather out of bounds

**Reported by @paulbrav.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The source maintainer merged the two-part long-context crash fix in PR #4.

**Issue state: closed, fixed.** The affected sparse-index consumer guard is patched in the source recipe's current main.

**Primary source.** [tonyd2wild DeepSeek-V4-Flash PR #4](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/pull/4), read on 2026-08-21; the PR links the full issue #2 investigation and A/B data.

**Symptom.** Long-context DeepSeek V4 serving eventually dies with a CUDA device-side assert or illegal memory access. The visible stack can wander because memory corruption may surface on a later kernel, making the first traceback look like a DSpark graph, MoE, or other innocent downstream path.

**Mechanism.** In the reported `compute_global_topk_indices_and_lens` path, `topk_indices_buffer` is persistent `torch.empty` storage. Padding tokens can therefore carry stale positive garbage. The affected Triton kernel loaded `is_valid_token` but gated the block-table gather only on `local_idx >= 0`; an invalid padding token with a large stale index could address past the request's block-table row or physically allocated KV blocks. The fix gates on token validity, bounds the block-table index and bounds the resulting block number by the actual KV cache allocation.

The source is explicit that this was **one of two stacked bugs**. Fixing this consumer OOB changed the failure from a raw illegal access to a caught downstream index assertion and increased survival, but did not by itself make the system stable. U24 records the second, load-bearing stale-slot mechanism separately.

**What we have not done.** We have not reproduced this kernel fault or independently inspected the exact base-image source used in the contributor's runs. We do not attribute all long-context DeepSeek failures to this one gather.

## If you have this stack

Pin the reported build and instrument the sparse-index consumer so every token records `is_valid_token`, `local_idx`, computed block-table index and final block number before the gather. Reproduce the long-context/churn workload with the original mask, then with validity plus allocation bounds, preserving the second DSpark slot guard state so the two mechanisms are not conflated.

**CONFIRM.** Invalid/padding tokens in the unpatched arm carry stale indices that would address outside the valid block-table/KV range, and the bounded arm prevents those accesses while leaving valid-token mappings unchanged.

**REFUTE.** No invalid token can reach the gather with an out-of-range index on the pinned build, or the same illegal access occurs at the same site with all consumer indices proven in bounds.

## Attribution

Reported, isolated and patched by @paulbrav; merged by the source repository maintainer in PR #4. The registry has not independently reproduced it.

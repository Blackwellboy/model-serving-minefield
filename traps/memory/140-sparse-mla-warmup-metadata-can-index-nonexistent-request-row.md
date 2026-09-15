# Trap 140: sparse-MLA metadata can index a request row that does not exist

**Found by Blackwellboy.**

**Status: measured here, raw not published.** The original failure was captured on a 2× DGX Spark / GB10 vLLM DeepSeek-V4 sparse-MLA lane and later recertified on a disposable RTX 3090 path after bounded hardening. The public upstream report is [vLLM issue #55636](https://github.com/vllm-project/vllm/issues/55636). Private regression/GPU logs remain unpublished.

**Symptom.** Sparse-MLA global-top-k mapping can consume metadata whose request-row selector names a row that does not exist in `block_table`. Depending on geometry and runtime state, the same invalid row selection can either silently map a token to the wrong KV slot or surface `cudaErrorIllegalAddress` in the Triton mapper.

In the historical failing build, synthetic CUDA-graph warmup produced metadata with request index `1` while `block_table.shape[0] == 1`, so row `1` was impossible. The full serving run failed in `_compute_global_topk_indices_and_lens_kernel`; a tiny standalone repro could instead return a wrong slot without raising.

Because CUDA errors are asynchronous, a later NCCL or synchronization point can report the sticky error even when the first invalid access happened in the sparse-MLA gather.

**Mechanism.** The consumer dereferences a block-table address derived from `req_idx` and `block_indices`. A complete safety contract therefore has two independent dimensions:

```text
0 <= req_idx < block_table_rows
0 <= block_idx < block_table_stride
```

The historical pinned lane also had a producer-side cardinality mismatch during synthetic CUDA-graph warmup: `token_to_req_indices` represented more request slots than the associated block table exposed. That producer mismatch is useful trigger evidence for the affected build, but it is not claimed as a current-main vLLM bug.

A later source re-check against vLLM `main` at `9cc7793e32f8340e111a6c822f231aa526a8ea21` found that current model-runner construction pads the block table to `num_reqs_padded` and fills CUDA-graph padding rows with `NULL_BLOCK_ID`, so the exact historical producer/cardinality mismatch appears avoided there. The downstream mapper still lacked both the request-row bound and the logical block-column bound in that re-check.

Invalid entries must map to `-1` and be excluded from the effective top-k length. **Do not clamp an invalid request index onto an existing row**: that can convert a crash into silent cross-request KV aliasing.

**Stacks and builds bitten.** The captured failure used DeepSeek-V4 Flash sparse MLA under vLLM `0.25.2.dev0+g752a3a504.d20260714`, Triton 3.6.0, PyTorch 2.11.0+cu130, TP=2 on 2× DGX Spark / GB10. The public issue documents the same failing geometry and a standalone wrong-slot reproduction. This entry does not claim every sparse-MLA or every CUDA illegal-address failure has this cause.

**The check.** Before the gather, validate both request-row and block-column geometry rather than checking only tensor existence or dtype:

```python
rows = block_table.shape[0]
assert token_to_req_indices.numel() == 0 or token_to_req_indices.min() >= 0
assert token_to_req_indices.numel() == 0 or token_to_req_indices.max() < rows
```

Then use a focused fixture where the block table has one request row while metadata attempts to address rows `[0, 1]`.

**TRAP PRESENT:** the invalid second request is dereferenced, maps to a wrong KV slot, or faults.

**TRAP ABSENT:** the invalid request is rejected/mapped to `-1`, excluded from the effective length, and the valid request still maps correctly.

Test the block-column bound separately; row-safe code can still be unsafe on the other dimension. For historical CUDA-graph reproduction, include padded warmup metadata. For current-main validation, keep the consumer-bound fixture even if producer construction no longer emits the historical mismatch.

**The fix.** On the affected historical build, repair the producer/consumer contract so warmup metadata cannot represent nonexistent request rows and independently harden the consumer on both dimensions. On current vLLM main, the producer-side mismatch is not presently reproduced, so the upstream fix scope should remain the defensive consumer bounds plus focused regressions unless a new producer regression proves otherwise.

The bounded internal recertification exercised row-bound and column-bound regressions, CUDA-graph-padding and normal-prefill checks, shipped-path regressions, and DeepSeek V4/V4.1 GPU paths without reproducing the original illegal address after the combined hardening. Two unrelated FlashMLA tests could not run in that checkout because `_C::scaled_fp4_quant` was unavailable; this entry does not call that unrelated full suite green.

**Fix/pin closure.**

- `BROKEN_PIN=vLLM 0.25.2.dev0+g752a3a504.d20260714`
- `REPRO_BEFORE=PASS`
- `FIXED_BY=historical lane hardened locally; current upstream consumer fix still open`
- `KNOWN_GOOD_PIN=UNKNOWN`
- `REPRO_AFTER=PASS` for the bounded local hardening; no public upstream known-good pin is claimed

**Claim boundary.** May claim that the historical pinned lane produced an impossible request-row selector, that the downstream mapper could turn it into either a wrong KV slot or an illegal access, and that the same mapper needs independent row and column bounds. May also claim that current-main source inspection no longer showed the same producer cardinality mismatch while the consumer remained insufficiently bounded at the cited revision. Must not claim that current vLLM main still has the historical warmup producer bug, that every sparse-MLA illegal address is this trap, or that an unpublished local patch is an upstream closing pin.

**Found.** 2026-09-07 during investigation of a DeepSeek-V4 sparse-MLA TP=2 CUDA illegal-address failure; bounded recertification completed 2026-09-12.

**Attribution.** Blackwellboy. Public upstream evidence: [vLLM #55636](https://github.com/vllm-project/vllm/issues/55636). Related but distinct from vLLM #49896, which concerns the other block-table dimension / bad local top-k indices rather than a nonexistent request row.

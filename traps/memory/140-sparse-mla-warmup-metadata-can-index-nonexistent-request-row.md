# Trap 140: synthetic sparse-MLA warmup metadata can index a request row that does not exist

**Found by Blackwellboy.**

**Status: measured here, raw not published.** The failure was first captured on a 2× DGX Spark / GB10 vLLM DeepSeek-V4 sparse-MLA lane and later recertified on a disposable RTX 3090 path after producer + consumer hardening. The public upstream report is [vLLM issue #55636](https://github.com/vllm-project/vllm/issues/55636); private regression/GPU logs remain unpublished.

**Symptom.** CUDA-graph warmup can create sparse-MLA request metadata where `token_to_req_indices` names a request row that has no corresponding row in `block_table`. The downstream Triton global-top-k mapper can then either read a wrong KV slot silently or surface `cudaErrorIllegalAddress`, depending on geometry/runtime state. In the captured failing state the metadata represented request index 1 while `block_table.shape[0] == 1`, so row 1 was impossible.

The hard failure can be misleading because CUDA errors are asynchronous: NCCL or another later synchronization point may report the sticky error even though the first invalid access was in the sparse-MLA gather.

**Mechanism.** The producer and consumer violated the same contract from opposite sides.

During synthetic CUDA-graph warmup, request indices were derived from request/query cardinality without proving that this cardinality matched the number of rows available in the associated block table. The sparse-MLA consumer then trusted `req_idx` and performed the block-table gather without a complete row bound. A column-only bound is insufficient: `req_idx=1` with one row is invalid even if the block index inside that imagined row is numerically small.

The required invariant is:

```text
query_slots == num_reqs == block_table.rows
```

The producer must construct/slice metadata so that invariant holds or fail closed. The consumer should independently enforce both dimensions before the gather:

```text
0 <= req_idx < block_table_rows
0 <= block_idx < block_table_stride
```

Invalid entries map to `-1` and must be excluded from the effective top-k length. **Do not clamp an invalid request index onto an existing row**: that can turn a crash into silent cross-request KV aliasing.

**Stacks and builds bitten.** First observed on DeepSeek-V4 Flash sparse MLA under vLLM `0.25.2.dev0+g752a3a504.d20260714`, Triton 3.6.0, PyTorch 2.11.0+cu130, TP2 on 2× DGX Spark / GB10. The upstream issue also records that current-main source inspection at the time still lacked the request-row bound in the consumer. A later bounded Track-B recertification exercised the producer + consumer fix on RTX 3090 and DeepSeek V4/V4.1 paths. This entry does not claim every sparse-MLA or every CUDA illegal-address failure has this cause.

**The check.** Before launching the gather, assert the producer/consumer geometry instead of checking only tensor existence or dtype:

```python
rows = block_table.shape[0]
assert token_to_req_indices.numel() == 0 or token_to_req_indices.min() >= 0
assert token_to_req_indices.numel() == 0 or token_to_req_indices.max() < rows
```

Then add a focused fixture where the block table has one request row while synthetic metadata attempts to address rows `[0, 1]`. The safe reference and hardened kernel must reject/map the second request to `-1`; a stock affected path that reads another slot or faults confirms the trap. Test column bounds independently as a second dimension.

For CUDA-graph coverage, include both padded warmup metadata and normal-prefill metadata. A fix that passes only the standalone Triton fixture is incomplete if the producer can still emit an impossible request/block-table relationship.

**The fix.** Repair both sides. Construct warmup metadata from the actual request count/block-table geometry, slice normal-prefill tables to the real request count, and fail closed on invariant mismatch. Keep consumer row + column bounds as defence in depth, returning `-1`/excluding invalid entries rather than clamping request identity.

The bounded Track-B validation reported 7/7 metadata regressions, row-bound and column-bound tests, CUDA-graph-padding and normal-prefill checks, 29/29 shipped-path regressions, DeepSeek V4/V4.1 GPU passes, and no reproduced illegal address after the combined patch. Two separate FlashMLA tests could not run because that checkout lacked `_C::scaled_fp4_quant`; this entry does not call that unrelated full suite green.

**Found.** 2026-09-07 during investigation of a DeepSeek-V4 sparse-MLA TP2 CUDA illegal-address failure; bounded recertification completed 2026-09-12.

**Attribution.** Blackwellboy. Public upstream evidence: [vLLM #55636](https://github.com/vllm-project/vllm/issues/55636). Related but distinct from vLLM #49896, which concerns the other block-table dimension / bad local top-k indices rather than a nonexistent request row.

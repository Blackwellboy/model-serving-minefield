# Trap 56: your KV-quant quality numbers never read the quantized cache

**Found by TheTom.**

**Status: reproduced here** (numbers before and after forcing chunked prefill differ; raw tables
held outside the tree and can be produced on request, per the default in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo)).

**Symptom.** You evaluate a KV cache quantization and the quality delta is suspiciously small, or
suspiciously large in the other direction, against older claims. Either way the number is not
measuring what the label says, because in a single-pass prefill the quantized cache may be **written
but never read back** within the measured window.

**Mechanism.** A quantized KV entry only costs you accuracy when a *later* query attends to it after
the round trip through the quantized representation. If your evaluation prefills the whole prompt in
one batch and then measures, most of the attention within that prefill can be served from values
that
never made the round trip. You measure a write path and call it a quality result.

Forcing **chunked prefill**: capping the batched-token count so later chunks must attend to earlier
chunks' *stored, quantized* entries, is what makes the quantized cache actually get read. On our
stack that meant setting `max_num_batched_tokens=512`.

The consequence for the literature is real: once measured this way, our own older docstring claims
("3-bit non-calibrated +20.59% perplexity") turned out to be **10 to 30x pessimistic** against
measurement on the current path, and had to be corrected in the same commit that fixed the harness.
A 4-bit calibrated-V configuration landed at **+0.19%**.

**Stacks and builds bitten.** vLLM with a KV-quant extension, measured with and without chunked
prefill on the same build and checkpoint. The general shape applies to any engine where prefill
batching is configurable and KV quantization is a separate feature, the two interact and neither
documents the interaction.

**The check.** Run the same perplexity or KL evaluation twice on the same build, changing only the
prefill batching:

```bash
# 1. default batching, the quantized cache may never be read back
<engine> --kv-cache-dtype <quant> ... ; run_eval

# 2. chunked, so later chunks must attend to stored quantized entries
<engine> --kv-cache-dtype <quant> --max-num-batched-tokens 512 ... ; run_eval
```

If the two disagree, the default-batching number is not a KV-quant result. Report the chunked one
and
say which batching produced it.

Complementary sanity check, from the other direction: confirm the KV type you asked for is the KV
type
you got. Guards and auto-upgrades can silently change it (a GQA-ratio guard promoting 3-bit K to
8-bit
is one we hit), and a build missing kernels for your K/V pair can silently fall back to CPU
([trap 46](46-fa-all-quants-cpu-fallback.md)). Log the **effective** per-tensor KV type, not the
flag.

**The fix.** Make chunked prefill part of the KV-quant evaluation protocol, and record
`max_num_batched_tokens` alongside every KV-quant quality number the way you would record context
length. A KV-quant table without a batching column is under-specified.

**Adjacent, worth stating.** The reverse error also exists: applying a compressed-V codec to a
*dense*
small model and reporting the resulting slowdown as a property of the codec. Attention is under 5%
of
decode on a dense 7B, so the codec is pure overhead there (pp512 fell from 1,494 to 217 tok/s) while
the same recipe wins on MoE and long-context shapes. Scope KV-quant claims to the architecture class
they were measured on.

**Found.** 2026-05, while reconciling quality claims that disagreed by more than an order of
magnitude.

**Attribution.** TheTom.


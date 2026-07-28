# Trap 45: wrong scale layout on FP4 dequant gives cosine 0.92 and a subtly broken model

**Found by TheTom.**

**Status: reproduced here.** Both layouts run, per-row cosine and generation compared; raw artifacts
held outside the tree and can be produced on request, per the default in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo).

**Sibling of [trap 27](27-nvfp4-accuracy-cliff-config-misses.md)**: same "serves fine, answers
garbage" signature, different mechanism, and this one is reproduced here rather than reported. Trap
27's mechanisms are all *serving-side* (ignore-list misses, engine-version kernel paths, non-native
hardware). This is the **offline** path: you gave up on native serving, decoded the checkpoint
yourself, and the decode is silently wrong.

**Symptom.** An offline dequantization "works." Weight cosine against the base reads **0.92**, which
looks close enough, and a one-line smoke test returns something plausible. Then the model emits
immediate EOS on trivial prompts, answers "which is larger, 9.9 or 9.11?" as **"9 and 9"**, and
produces mangled tokens on longer generations. Benchmarks run on it look like a real quality
regression from quantization.

**Mechanism.** The checkpoint stores its per-group FP8 scales in **linear (unswizzled)** layout, but
the reference dequant helper defaults to a **swizzled** read. The wrong layout scrambles which scale
applies to which group. The damage is distributed rather than catastrophic, so aggregate cosine
stays
high enough to pass a casual sanity check while the model is functionally destroyed.

| setting | weight cosine vs base | behavior |
|---|---|---|
| `swizzle=True` | 0.92, *looks plausible* | immediate EOS; "9.9 vs 9.11" to "9 and 9"; mangled tokens |
| `swizzle=False` | **0.9967** | correct capital, correct decimals, real code |

**cosine 0.92 is a destroyed 64-layer model, not a close one.** Small per-layer error compounds.

**Stacks and builds bitten.** NVIDIA modelopt NVFP4 checkpoints (W4A16, group size 16) decoded with
the vendor `dequantize_to_dtype(...)` helper. Observed while producing a bf16 proxy of
`Qwen3.6-27B-NVFP4` because native FP4 serving was broken on that hardware (separate trap). Layout
assumption is checkpoint-side, so it is not specific to one engine.

**The check.** Three assertions, all cheap, in this order:

1. **Per-row cosine in float64**, not a flat cosine over the whole tensor. A flat cosine over a
   1.27B-element `lm_head` overflows in float32 and can return **> 1**, which is itself the tell
that
   your metric is broken.
2. A **decimal-comparison generation probe** (`is 9.9 or 9.11 larger?`) alongside the usual
   capital-of-France probe. The capital probe passes on a subtly-broken dequant; the decimal probe
   does not.
3. Compare against the **base** model's own output on the same prompts, not against your
expectation.

Runnable: [`checks/dequant_fidelity.py`](../../checks/dequant_fidelity.py).

```
$ python3 checks/dequant_fidelity.py --base $BASE --dequant $OUT --sample-rows 4096
  per-row cosine p01/p50: 0.9931 / 0.9967   PASS (>=0.995)
  generation probes: capital=PASS  decimal=PASS  eos-immediate=PASS
```

**The fix.** Read the checkpoint's actual scale layout rather than trusting the helper default; for
linear storage that is `swizzle=False`. Then multiply by the fp32 global scale
(`weight_scale_2`). Per-tensor-class handling that worked:

- W4A16 tensors: `.weight` uint8 + `.weight_scale` fp8 + `.weight_scale_2` fp32 to dequantize with
  `swizzle=False`, then apply the global scale.
- FP8 tensors: `w.to(float32) * weight_scale`.
- Embeddings, norms, conv1d, MTP/draft heads: copy unquantized.

**Do not publish behavioral numbers from a dequant proxy without saying what it is.** Ours was
weight-only (bf16 activations, no runtime FP8 KV), which is the *optimistic* bound, and the writeup
says so.

**Found.** 2026-07-02, while building a serving workaround; the 0.92 run had already produced a
partial behavioral result before the decimal probe caught it.

**Attribution.** TheTom.

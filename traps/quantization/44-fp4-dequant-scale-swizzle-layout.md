# Trap 44: wrong scale layout on FP4 dequant gives cosine 0.92 and a subtly broken model

**Found by TheTom.**

**Status: contributor-measured, conditions as reported.** Measured by the contributor on their own hardware; conditions are stated in the entry. Not independently reproduced here. Raw is private and available to maintainers on request, which is why this is not 'reproduced here' (see [CONTRIBUTING](../../CONTRIBUTING.md#status-vocabulary)).

**Sibling of [trap 27](27-nvfp4-accuracy-cliff-config-misses.md)**: same "serves fine, answers
garbage" signature, different mechanism. Trap
27's mechanisms are all *serving-side* (ignore-list misses, engine-version kernel paths, non-native
hardware). This is the **offline** path: you gave up on native serving, decoded the checkpoint
yourself, and the decode is silently wrong.

*(Corrected 2026-07-28: this paragraph previously read "and this one is reproduced here rather than
reported", which contradicted the entry's own status line. It is contributor-measured and has not
been reproduced here. The stale clause dates from the documentation bug described in the
[CHANGELOG](../../CHANGELOG.md) for the 43-to-55 merge, where the vocabulary was defined loosely
enough that the contributor reasonably self-labelled these entries "reproduced here"; that was our
error and not his. No measurement in this entry changed.)*

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

## The wider mechanism, from upstream documentation

The instance above is one checkpoint and one helper's default. The reason it is
worth generalising is that **there is no single FP4 scale layout to be right
about**, and the differences are documented by the libraries themselves. This
section cites primary documentation only; nothing in it is measured here, and
none of it changes this entry's status.

**1. The two FP4 formats do not share a scale type or a block size.** NVIDIA's
CUTLASS documentation gives NVFP4 the scale-factor type `float_ue4m3_t` and
MXFP4 the type `float_ue8m0_t`, described respectively as unsigned with 4
exponent and 3 mantissa bits, and unsigned with 8 exponent and 0 mantissa bits.
The block sizes differ too: `nv_float4_t` carries a "scale factor vector size
(16 or 32)" against `mx_float4_t`'s "(32 or 64)", dense variants taking the
smaller value. FlashInfer's `mm_fp4` states the same split from the API side:
`block_size` accepts "only 16 and 32", "16 in case of nvfp4 quantization. 32 in
case of mxfp4 quantization". So a kernel written for one format and handed the
other misreads both *which* scale applies to a group and *how many* elements
that group covers. A file named for one format is not evidence of which one a
kernel expects.

**2. The layout differs per backend, not just per format.** FlashInfer's
`mm_fp4` documents different weight-preparation requirements per backend:
`cudnn`, `cutlass` and `cute-dsl` want the 128x4 layout with `do_shuffle=False`,
while `trtllm` wants `do_shuffle=True` for the B matrix and accepts either 128x4
or 8x4 for A. Its quantization module exposes an `SfLayout` enum and separate
swizzled and "linear (non-swizzled)" paths, and its backend `auto` mode selects
differently on SM120 than on other architectures. CUTLASS documents the
corresponding on-disk structure as a "512B basic-block" of "128 M/N dimension
and 4 scale factors (SF) along the K dimension", with `Sm1xxBlockScaledConfig`
provided to build it. The layout is therefore a property of the *consumer*, and
a checkpoint is only correct relative to the one that reads it.

**Why this compounds the measured instance.** The failure above needed only a
helper defaulting to swizzled where the file was linear. Everything in this
section is another way to land the same mismatch without touching a
`swizzle=` argument: pick the backend whose layout convention differs, or feed
an MXFP4-shaped artifact to an NVFP4 kernel. The detection is unchanged and is
the reason the checks below are worth running whatever path you took:
per-row cosine in float64, plus a discriminative generation probe.

**Deliberately not stated here.** The secondary review that prompted this
section also claimed that reading FP8 scales as FP6 corrupts every block. **No
primary source was found for it, and the sources above point the other way**:
both documented scale types, `ue4m3` and `ue8m0`, are 8-bit, and FlashInfer
gives the scale dtype as `float8_e4m3fn` or `uint8`. FP6 appears nowhere in the
block-scale path, so that claim is omitted rather than repeated. Likewise no
figure, ranking or frequency claim from that review is carried here.

Sources, all vendor documentation:
[CUTLASS Blackwell functionality](https://github.com/NVIDIA/cutlass/blob/main/media/docs/cpp/blackwell_functionality.md),
[FlashInfer `mm_fp4`](https://docs.flashinfer.ai/generated/flashinfer.gemm.mm_fp4.html),
[FlashInfer quantization API](https://docs.flashinfer.ai/api/quantization.html).
Checked 2026-07-28.

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

**Check script.** The runnable version of this check is in review separately: every check in this repo must declare the negative and empty-set controls described in [the check contract](../../checks/README.md), and this one does not yet. The assertion above is the check; the script is a convenience wrapper for it.

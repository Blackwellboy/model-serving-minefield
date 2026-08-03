# Trap 109: an NVFP4 requant that leaves the MTP experts in the source format serves cleanly and quietly breaks its own drafter

**Found by Blackwellboy.**

**Status: measured here, raw not published** for the acceptance collapse and
the recovery, which came from our own lane's `/metrics` counters and bench
harness and are not shipped. The checkpoint-layout facts are separately
checkable by a stranger: both the broken and the fixed layout are public
revisions of
[Rarri/DeepSeek-V4-Flash-0731-NVFP4](https://huggingface.co/Rarri/DeepSeek-V4-Flash-0731-NVFP4),
and the fix ships its own conversion report
(`mtp_nvfp4_build_report.json`) and quantized-layer manifest
(`hf_quant_config.json`) in the repo. The two statuses are stated separately
so neither borrows the other's strength.

**Symptom.** A quantized MoE checkpoint serves with multi-token-prediction
speculative decoding enabled. The server boots green, output is coherent at
every temperature, nothing is logged as a warning. But cumulative draft
acceptance sits at **14.7%** against a vendor-published figure of 50.8% for
this model family, and single-stream decode with speculation **on** runs
*below* the same lane with speculation **off** (medians 100 to 103 tok/s
against a 116.7 tok/s no-speculation baseline on the same harness).
Speculation is a pure tax and nothing announces it.

**Mechanism.** The requant quantized the routed experts of the 43 main MoE
layers to NVFP4 and deliberately excluded the MTP layers, leaving their
expert weights in the source release's MXFP4 format (E2M1 nibbles with E8M0
block scales). The serving stack's NVFP4 fused-MoE path loads the MTP layers
through the same code path as the main layers, and MXFP4 tensors read as
NVFP4 do not error: the shapes are compatible enough to load and wrong
enough to produce a drafter whose proposals the target almost always
rejects. The target model is untouched, so quality probes pass. The only
observable is the acceptance counter, and only if you know what it should
read.

The misdiagnosis wrinkle cost more time than the bug. The first run against
a corrected checkpoint used the stack's probabilistic draft sampling method
and produced garbled output, so the fix was recorded as broken and rolled
back. On this build and lane the greedy draft sampling method is clean at
target temperature 0, 0.7 and 1.0 including thinking mode, and the
probabilistic method garbles. Note the inversion against
[trap 62](../runtime/62-spec-decode-garble-under-wrong-drafter-config.md),
where the stable configuration on a different lane is the probabilistic
method: which drafter sampling method is safe is a property of the build and
lane, not of speculative decoding, and the only way to know yours is to test
both.

**The fix, and what it measured.** Recast the MTP-layer routed-expert
weights from MXFP4 to NVFP4 with the same closed-form scale mapping used for
the main layers. The cast is exact: 2,304 tensors, 603,979,776 of
603,979,776 blocks bit-identical after conversion, maximum dequantization
error 0.0, per the conversion report shipped with the checkpoint. With the
recast checkpoint and the greedy draft method, the same lane and harness
measured:

| | broken checkpoint | recast checkpoint |
|---|---:|---:|
| cumulative draft acceptance | 14.7% | 49.4% |
| mean acceptance length (of 6) | | 3.85 |
| single-stream decode vs no-spec baseline | below baseline | 1.78x median, 1.96x mean |

Vendor-published acceptance for this family's drafter is 50.8%, so 49.4% is
recovery to expected behaviour, not a tuning triumph.

**Stacks and builds bitten.** A vLLM-derived build with a CUTLASS NVFP4
fused-MoE backend serving a DeepSeek-V4-Flash-0731 hybrid FP8 + NVFP4
checkpoint, tensor parallel 2 on 2x RTX PRO 6000 Blackwell (96 GB, sm_120),
x86, CUDA 13, PCIe without peer-to-peer. The checkpoint is first-party:
[Rarri/DeepSeek-V4-Flash-0731-NVFP4](https://huggingface.co/Rarri/DeepSeek-V4-Flash-0731-NVFP4),
derived from `deepseek-ai/DeepSeek-V4-Flash-0731` at `7872f01b`. Scope the
mechanism to stacks that route draft-model layers through the same
quantized-MoE path as target layers; the general lesson (a requant's
exclusion list can break a component that only shows up in a counter) is
portable.

**The check.**

1. Read the requant's own manifest before serving it. If
   `hf_quant_config.json` (or the stack's equivalent) excludes `mtp.*` or
   any draft-model module while the launch line enables speculative
   decoding, you are in this trap's territory: the drafter will run on
   weights the quantized path was never given in its own format.
2. After a real workload, scrape the engine's speculative counters
   (`spec_decode_num_accepted_tokens_total` over
   `spec_decode_num_draft_tokens_total`). Compare against the vendor's
   published acceptance for the family. A large shortfall (here, 14.7%
   against 50.8%) with clean output is the signature; do not wait for an
   error, because there is none.
3. A/B the draft sampling method on your own lane before concluding
   anything from garbled output. Thirty structured-output generations per
   method, scan the raw bodies. See trap 62 for the scan.

**Found.** 2026-08-03, while chasing why a speculative lane that should have
doubled decode was losing to its own baseline; the 14.7% figure had been
misattributed to drafter tuning for two days.

**Attribution.** Blackwellboy. Conversion report and manifest are in the
checkpoint repo; acceptance and throughput numbers are ours.

**Related.**
[Trap 62](../runtime/62-spec-decode-garble-under-wrong-drafter-config.md)
(drafter sampling method garble, with the opposite safe setting on a
different lane),
[trap 28](../runtime/28-mtp-fails-only-under-concurrency-or-temperature.md)
(speculative paths green on the axes you tested and broken on the ones you
did not),
[trap 10](10-quant-label-is-not-the-kernel-path.md) (the label on the
checkpoint is not the path the kernels take),
[trap 111](../evaluation/111-greedy-spec-decode-medians-are-a-content-lottery.md)
(how to read throughput numbers from the recovered lane).

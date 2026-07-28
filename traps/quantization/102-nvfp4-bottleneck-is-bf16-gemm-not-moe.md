# Trap 102: NVFP4 MoE profiling says "speed up the MoE" but the bottleneck is BF16 GEMMs

**Found by Nemo (@NemoSMF), based on profiling by @Hikari_07_jp.**

**Status: contributor-measured, conditions as reported** (self-CUDA profile on
2× RTX PRO 6000, published in the
[Hikari-knowledge vault](https://github.com/hikarioyama/Hikari-knowledge/blob/main/nodes/serving/step37-single-stream-ceiling.md)).

**Symptom.** You serve an NVFP4-quantized MoE model and profile it to find the
bottleneck. The profiler shows the MoE path is only ~22% of decode time while
BF16 GEMMs are ~44%. You speed up the MoE path (better kernel, different
quantization) and throughput barely moves. The model seems "stuck" at a ceiling
that no serving flag can break.

**Mechanism.** Weight-only linear dequantization feeds BF16 GEMMs, while selected
attention projections remain BF16 for accuracy. The BF16 GEMMs are the dominant
cost, not the NVFP4 MoE path. Speeding the MoE path alone cannot remove the
dominant cost — a larger gain requires changing model quantization (e.g.,
requantizing the output projection), not merely adjusting a serving flag. The
profiling data makes this visible, but the intuition "it's a quantized MoE, the
MoE must be the bottleneck" leads people to optimize the wrong layer.

**Stacks and builds bitten.** Step3.7 198B NVFP4, 2× RTX PRO 6000, TP=2, MTP
K=1, vLLM. Self-CUDA profile: BF16 CUTLASS GEMMs 44%, NVFP4 MoE 22%, attention
14%, TP all-reduce 16%. Reported ceiling: ~127 tok/s single-stream. A selective
output-projection requantization improved throughput to 137.4 tok/s (+7.65%) but
was rejected due to a +6.4% NLL change per token.

**The check.** Profile before optimizing:

```bash
# Run a self-CUDA profile on a representative decode batch
# (syntax varies by stack; this is the pattern)
python3 -c "
import torch
# ... load model, warm up ...
with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CUDA]) as prof:
    # run a decode step
    pass
print(prof.key_averages().table(sort_by='cuda_time_total', row_limit=10))
"
# If BF16 GEMMs are >40% and your MoE path is <25%, you are optimizing
# the wrong layer. The fix is model requantization, not a serving flag.
```

**The fix.** If the profile shows BF16 GEMMs as the dominant cost, the path to
higher throughput is requantizing the BF16 projections to a lower precision —
not tuning the MoE kernel. This requires an explicit quality budget: in the
tested case, output-projection requantization gained +7.65% throughput at a
+6.4% NLL cost, which was rejected. The trade-off is real and must be measured,
not assumed. No serving flag can substitute for it.

**Found.** 2026-07-04 (profiling date from Hikari-knowledge), cross-referenced
by Nemo during SMF Works deployment planning.

**Attribution.** Profiling by @Hikari_07_jp, published in the
[Hikari-knowledge vault](https://github.com/hikarioyama/Hikari-knowledge/blob/main/nodes/serving/step37-single-stream-ceiling.md).
Cross-referenced and contributed by Nemo (@NemoSMF). The Hikari-knowledge vault
is a public, curated knowledge graph of measured serving results.
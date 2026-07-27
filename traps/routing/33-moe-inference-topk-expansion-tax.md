# Trap 33: raising a MoE's inference top-k silently costs accuracy

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([reports/ALPHA_DIAL_20260712.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/reports/ALPHA_DIAL_20260712.md)).**

**Status: reported by others.** Measured by the finder across three runs on
two machines; the per-item JSON he publishes was re-scored here and the dose
curve confirmed from his raw. Not yet run on our own hardware; queued
against our Qwen 3.6 35B-A3B NVFP4 lane.

**Symptom.** You raise the number of experts a MoE activates per token,
because more active parameters should mean more capability, and the model
gets **worse**. No error, no warning, no log line. The checkpoint is
untouched, the experts are fine, and the benchmark drops several points. The
change is one config value, so nothing looks like it could have gone wrong,
and the obvious reading, "this model does not benefit from more compute", is
the wrong one.

**Mechanism.** The selected gate scores are renormalized to sum to 1. Adding
24 more experts to that normalized mixture does not add their contribution on
top of the original eight, it **dilutes** the weight the original eight
receive. The expert selection is not damaged and the routing is not
degraded: the nesting is exact, so the top-8 of a k=32 selection are the same
8 experts a k=8 selection would have picked. Only the mixing ratio changed.
The finder's worked example, for one token where the top 8 hold 18% of
pre-top-k mass and ranks 9 to 32 hold 20%: rank-1 expert A takes 6/18 = 33.3%
of the mixture at k=8, and 6/38 = 15.8% at k=32. The tail experts are
untrained at that weight and spend the mixture on nothing.

The phenomenon is not new. Elastic MoE (arXiv:2509.21892) reports the same
degradation as an "inference-time scaling wall" and fixes it during training.
What is worth knowing here is that it is silent, it is a serving-side config
change people make casually, and it has a runtime fix.

**Stacks and builds bitten.** Qwen3.6-35B-A3B (256 experts per layer, native
top-8), revision `995ad96eacd98c81ed38be0c5b274b04031597b0`, bf16 under HF
transformers on 2x RTX PRO 6000. MMLU and GSM8K scored by choice-logprob
(no generation, so no truncation), n=600, shuffle seed 0, batch 16, paired on
identical items. Three separate runs are in his log and they are **not** one
measurement; each is stated on its own terms:

- **k dose sweep** (local, per-item JSON published as
  `esft/reports/eval/base_k{8,16,24,32}_intel_items.json`; recomputed here,
  same 600 items with identical gold verified across arms). MMLU: k8
  506/600 (84.33%), k16 497 (82.83%), k24 489 (81.50%), k32 484 (80.67%);
  k8 to k32 is **-3.67 pt**, discordant 35/13, exact paired p=0.0021.
  GSM8K: k8 536/600 (89.33%), k16 533 (88.83%), k24 527 (87.83%), k32 519
  (86.50%); k8 to k32 is **-2.83 pt**, discordant 31/14, exact paired
  p=0.016. Monotone in k on both benchmarks.
- **2026-07-11, gpu-host, four arms serial.** base@k8 85.00% vs base@k32
  81.83%, **-3.17 pt**, CI95 [-5.53, -0.80], exact paired p=0.013.
- **2026-07-12 and 2026-07-16, local.** base@k8 84.67% (508/600) vs base@k32
  81.50% (489/600), **-3.17 pt**; restated 2026-07-16 with exact paired
  p=0.009.

Note for anyone citing this: the counts `508/600 vs 489/600` and the p-value
`0.013` come from **different runs** and are paired together in the source
README. The two runs agree on the effect size to two decimals, which is the
stronger claim; cite the counts with p=0.009 or the p=0.013 with the 85.00 /
81.83 pair, not crosswise.

**The check.** Before you change a MoE's active-expert count, measure both
settings on the same items, paired, and report the delta. If you are not
running a benchmark, the cheap structural check is to confirm what your
serving stack does with the extra experts: dump the post-selection gate
weights for one token at both k values and compare the weight assigned to the
rank-1 expert. If it fell, you bought dilution, not capacity.

```python
# after top-k selection, before the expert matmul
w8  = softmax_selected_weights(scores, k=8)
w32 = softmax_selected_weights(scores, k=32)
assert w32[argmax] < w8[argmax]   # the tax, visible in one token
```

Note also that top-k is a **train-time** property of the checkpoint. A model
pretrained at top-8 has never seen ranks 9 to 32 carry real weight, so this
is expected behavior, not a bug in the server.

**The fix.** Either leave top-k at the trained value, or scale the tail back
down. The finder's runtime operation, which he calls the alpha dial
(`--router-tail-scale`, implemented as a ~20-line gate forward hook, no
weight change): rank the selected gate scores per token, multiply ranks 9
through 32 by alpha, renormalize.

- `alpha = 1` is plain k=32.
- `alpha = 0` is mathematically identical to k=8, and measures that way:
  98/100 identical predictions against base@k8, at the bf16 noise level.
- Sweeping alpha on the base model (MMLU n=600, same items, paired against
  alpha=1) repays the whole tax with **zero training**: alpha=0 84.67,
  alpha=0.25 84.33 (+2.83 [+0.97, +4.70]), alpha=0.5 84.50 (+3.00 [+1.35,
  +4.65]), alpha=0.75 82.83 (+1.33 [+0.12, +2.55]), alpha=1 81.50. Flat on
  [0, 0.5], then it collapses.
- alpha=0.5 was checked for harm on two other axes, base against base,
  paired: JMMLU n=600 80.17% vs 78.83% (-1.33 pt, p=0.31, ns) and GSM8K
  n=400 generation 84.75% vs 85.75% (+1.00 pt, p=0.63, ns).

Two caveats if you port the hook. It hardcodes the rank boundary at 8, so it
is correct only for a model whose native top-k is 8; parameterize that against
the checkpoint's `num_experts_per_tok` before reusing it. And the dial
recovers the floor, it does not beat it: at best the model returns to its
k=8 accuracy while paying k=32 compute. Raising top-k is only worth the
tokens if you are also training the tail.

**Found.** 2026-07-11 (the tax, first measured under choice-logprob scoring)
and 2026-07-12 (the dial and the sweep), in the finder's public research log.

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
who published the mechanism, the sweep, the per-item JSON, and the negative
results around them. Prior art for the phenomenon: Elastic MoE
(arXiv:2509.21892). Dose-curve re-scoring from his published per-item JSON
by Blackwellboy.

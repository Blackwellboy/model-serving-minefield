# Trap 35: identical weights do not give identical scores

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([DEVLOG.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/DEVLOG.md),
2026-07-08 and 2026-07-12 entries).**

**Status: reported by others.** Measured by the finder on two machines; a
third value for the same nominal measurement was found here while reading his
published run artifacts.

**Symptom.** You re-run a benchmark you already ran. Same weights, same
revision, same benchmark, same item count, same protocol, different box (or
just a different day), and the number moves by half a point. You start
looking for what changed in the checkpoint. Nothing changed in the
checkpoint. Worse, a half-point drift is exactly the size of the effect many
people publish, so a comparison assembled from two runs on two machines can
manufacture or erase a result on its own.

**Mechanism.** Nothing exotic: bf16 accumulation order, kernel selection,
batch composition, and library versions differ per host, and greedy decoding
is only deterministic within a fixed kernel path. The scores are not
reproducible to the last item across machines, and they are not reproducible
to the last point across runs. The trap is not that this happens, it is that
people assume it does not, and then compare arm A measured on Monday's box
with arm B measured on Tuesday's.

The finder measured the disagreement directly rather than assuming it:
**98.7% item-level agreement** between two machines running the same model on
the same items (a 0.33 pt score difference). That is the noise floor for any
cross-machine comparison on this stack. He used the same figure as a
calibration anchor elsewhere: when he verified that his `alpha=0` setting was
mathematically identical to k=8, he got **98/100 identical predictions** and
correctly read that as bf16 noise rather than as a bug, precisely because he
already knew what same-weights agreement looks like.

The drift is visible in his numbers too. `base@k8` on MMLU, n=600,
choice-logprob, nominally the same measurement, reads three different values
across his log and shipped artifacts:

| Where | base@k8 MMLU |
|---|---|
| k-sweep run, local (per-item JSON) | 84.33% (506/600) |
| 2026-07-12 boundary run, local | 84.67% (508/600) |
| 2026-07-11 four-arm run, gpu-host | 85.00% |

A 0.67 pt spread on identical weights and a nominally identical protocol.
On a second benchmark the same day, GSM8K read 0.887 on one host and 0.893
on the other.

**Stacks and builds bitten.** Qwen3.6-35B-A3B revision
`995ad96eacd98c81ed38be0c5b274b04031597b0`, bf16, HF transformers, two hosts
(8x RTX PRO 6000 and a 2-GPU local box), MMLU/GSM8K by choice-logprob with
no generation, n=600, shuffle seed 0. The class is stack-independent and
gets worse, not better, with generation-based benchmarks, where sampling and
truncation add their own variance.

**The check.** Measure your own agreement floor before you trust any small
delta. Run the **same** model twice, on the two machines (or the two
sessions) you actually intend to compare across, on the same items, and
report per-item agreement, not just the score:

```python
agree = sum(a["correct"] == b["correct"] for a, b in zip(run1, run2))
print(f"{agree}/{len(run1)} item agreement, "
      f"score delta {mean_a - mean_b:+.2%}")
```

If that agreement is 98.7%, then any effect smaller than roughly the
resulting score spread is inside your noise and needs a same-machine paired
re-run before you publish it.

**The fix.** Fix one machine as the measurement room and run every arm of a
comparison there, serially, in one session. The finder made this an explicit
operating rule after seeing the drift: one host is designated the evaluation
machine and all paired verdicts are produced on it. When a cross-machine
comparison is unavoidable, state both hosts next to the number and treat the
agreement floor as the minimum detectable effect. Do not assemble a paired
verdict from arms measured on different boxes; his harness enforces this by
refusing paired-verdict runs whose arms disagree on model path, which pushed
cross-model comparisons to an explicit manual path instead of a silent one.

**Found.** 2026-07-08 (cross-host score drift noticed and re-measured
same-machine) and 2026-07-12 (the 98.7% agreement figure, taken deliberately
as a validity check on a cross-machine comparison).

**Attribution.** [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b),
who measured the agreement floor instead of assuming determinism and who
published the per-item JSON that made the three-way spread visible. Third
value identified by Blackwellboy while re-scoring his shipped artifacts.

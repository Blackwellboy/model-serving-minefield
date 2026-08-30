# Trap 35: identical weights do not give identical scores

**Found by [@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)
([DEVLOG.md](https://github.com/hikarioyama/qwen36-a6b/blob/main/DEVLOG.md),
2026-07-08 and 2026-07-12 entries).**

**Status: reproduced here.** Originally reported and measured by the finder on
two machines, and his remains the originating report; a third value for the same
nominal measurement was found here while reading his published run artifacts.
Independently reproduced on our own hardware on 2026-07-28, on a different build
class, with a first-party agreement floor. Our measurement also **generalises**
the trap: the disagreement does not need two machines, it appears between two
passes of a single server process.

**Evidence.** First-party raw (six answer sheets), the serial scorer and an
independent re-derivation script are in
private evidence archive *(private evidence archived)*;
the write-up is
here *(private evidence archived)*.
The finder's evidence is his DEVLOG and the per-item JSON linked above.

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

**Reproduced here, 2026-07-28.** Qwen3.6-35B-A3B in an **NVFP4** build
(revision `491c2f1e`) under **vLLM** nightly `a346d589`, image `a720df3e84a8`,
on two GB10 nodes, tensor-parallel 1. Weights byte-identical on both nodes
(per-file sha256 manifests hashing to `c4b017ad`). MMLU `all`/`test`, shuffle
seed 0, first 600, generation-scored to a single letter with thinking off,
greedy (temperature 0, top_p 1, max_tokens 16), one request in flight, prefix
caching off. Six pairings of four identical-configuration runs:

| pair | kind | agreement |
|---|---|---|
| same process, scored twice | within-process | 97.33% |
| same node, fresh server process | restart | 97.50% and 97.33% |
| two nodes, identical image and args | cross-machine | 97.17%, 97.83%, 98.33% |

**Pooled 3513/3600 = 97.58%**, so 2.4% of items flip between runs that differ
in nothing. Same phenomenon as the finder's 98.7%, same order of magnitude,
slightly worse on a quantized vLLM path.

The structural finding is that **the cross-machine pairs straddle the
within-process pair.** There is no separation between them. Machine identity
is not the variable; the nondeterminism lives inside one server's execution.
Speculative decoding was ruled out as the cause: disabling MTP moved
within-process agreement from 97.33% to 98.17% with heavily overlapping Wilson
intervals, and that arm produced the largest single score swing seen anywhere
in the set (1.00 pt between two passes of one server).

Score-level, the four identical runs read 513, 512, 516 and 514 out of 600, a
0.67 pt spread. The resulting calibration, **plus or minus 1.3 points at
n=600**, is the minimum detectable effect we now cite for MMLU-style paired
comparisons on that stack. It is an accuracy delta over four-way
multiple-choice items and does **not** transfer to binary-outcome results such
as firing-rate counts, which have their own and much wider binomial noise.

**Stacks and builds bitten.** Qwen3.6-35B-A3B revision
`995ad96eacd98c81ed38be0c5b274b04031597b0`, bf16, HF transformers, two hosts
(8x RTX PRO 6000 and a 2-GPU local box), MMLU/GSM8K by choice-logprob with
no generation, n=600, shuffle seed 0. The class gets worse, not better, with
generation-based benchmarks, where sampling and truncation add their own
variance.

Also bitten: Qwen3.6-35B-A3B revision `491c2f1e`, **NVFP4**, **vLLM** nightly
`a346d589`, two GB10 nodes, MMLU generation-scored to a single letter, n=600,
shuffle seed 0. That the class shows up on a quantized vLLM generation path at
the same magnitude as on a bf16 transformers logprob path is the practical
evidence for it not being a property of one serving stack.

**Scope of that generalisation, stated exactly.** Both measurements are
**Qwen3.6-35B-A3B**. What varied across them was the serving stack (HF
transformers and vLLM), the numeric format (bf16 and NVFP4), the scoring
method (choice-logprob and generation to a single letter) and the hardware
class (RTX PRO 6000 and GB10). What did **not** vary was the model family, so
this says the effect is not an artifact of one stack, and it does **not**
establish a magnitude for any other family. The mechanism (accumulation
order, kernel selection, batch composition) has no reason to be
family-specific and we expect it to generalise, but expecting is not
measuring. Measure your own floor on the model you are actually comparing,
which is what the check below is for. This is the same caution as the MDE
non-transfer note above, and for the same reason.

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
re-run before you publish it. Two independent measurements of this
floor now exist, 98.7% and 97.58%, so if you have not measured your own, assume
you are somewhere near them rather than at 100%.

Run the same check **twice on one machine** as well. That is the version most
people skip, and on our stack it returns the same floor as the cross-machine
one.

**The fix.** Fix one machine as the measurement room and run every arm of a
comparison there, serially, in one session. The finder made this an explicit
operating rule after seeing the drift: one host is designated the evaluation
machine and all paired verdicts are produced on it. When a cross-machine
comparison is unavoidable, state both hosts next to the number and treat the
agreement floor as the minimum detectable effect.

Necessary, but on our measurement **not sufficient**: designating one
evaluation machine removes a variable that turned out not to be the dominant
one. A single machine running arms serially still has a floor, and on our stack
it is the same floor. Measure it and quote it; do not treat same-machine serial
execution as though it bought determinism. Do not assemble a paired
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

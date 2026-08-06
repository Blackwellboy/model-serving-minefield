# Greedy is not reproducible on this stack

**Queue item:** Q2 of the
[qwen36-a6b verification queue](2026-07-28-qwen36-a6b-verification-queue.md).
Not a claim to confirm or refute: the output is our own number, measured so
that every paired comparison we publish has a stated noise floor underneath it.

**Result.** Two passes of the **same server process**, greedy, at concurrency
1, with prefix caching off, disagree on **2.4% of items**. Re-running changes
the answer sheet. Determinism is not a property this serving path has, and it
does not become one by setting temperature to 0.

**Date:** 2026-07-28. Two GB10 test lanes, no production lane touched.

## The structure of the result, which matters more than the headline number

Six pairings of four identical-configuration runs over the same 600 items:

| pair | kind | agreement | discordant (A+/B-) | score delta |
|---|---|---|---|---|
| srv1 pass1 vs srv1 pass2 | within-process | 584/600 = 97.33% | 7/6 | +0.17 |
| srv1 pass1 vs srv2 pass1 | restart, same node | 585/600 = 97.50% | 5/8 | -0.50 |
| srv1 pass2 vs srv2 pass1 | restart, same node | 584/600 = 97.33% | 5/9 | -0.67 |
| srv1 pass1 vs node B | cross-machine | 583/600 = 97.17% | 6/7 | -0.17 |
| srv1 pass2 vs node B | cross-machine | 587/600 = 97.83% | 3/5 | -0.33 |
| srv2 pass1 vs node B | cross-machine | 590/600 = 98.33% | 5/3 | +0.33 |

**Pooled: 3513 of 3600 item-pairs agree, 97.58%.** Range 97.17% to 98.33%.

Three things follow, and the second is the one that changes how you design an
A/B:

**1. Machine identity is not the variable.** The three cross-machine pairs
(97.17%, 97.83%, 98.33%) *straddle* the within-process pair (97.33%). There is
no separation. Two different boxes agree with each other exactly as well as one
process agrees with itself. Whatever is moving lives inside a single server's
execution, not between hosts.

This has a practical consequence we cared about. Some comparisons cannot be
interleaved: if the thing under test is read from the checkpoint at load time,
each arm is a separate server start, and the arms are therefore separated in
time and possibly across machines. That is usually described as a weaker design
than an interleaved one. On this evidence it costs nothing measurable. Restart
pairs sit at the within-process floor, and so do cross-machine pairs.

**2. Speculative decoding is not the cause.** MTP with 3 speculative tokens was
the obvious suspect. With it disabled, two passes of one server agreed on
98.17% against 97.33% with it on. That is a nudge in the expected direction and
nothing more: the Wilson intervals overlap heavily (96.75 to 98.97 against 95.71
to 98.35), and the MTP-off pair produced the single largest score swing we
observed anywhere, a full 1.00 point between two passes of the same server.
Turning speculative decoding off does not buy a clean floor.

We did not chase the mechanism further. The remaining candidates are the usual
ones, non-associative floating point reduction order in the MoE and attention
kernels and batch-shape-dependent kernel selection, and separating them is a
kernel-level investigation rather than a lane-hours one.

**3. The aggregate is far steadier than the item.** A 2.4% item-flip rate
sounds worse than it is for score-level reporting, because the flips are
near-symmetric: the discordant splits above run 7/6, 5/8, 5/9, 6/7, 3/5, 5/3.
The four runs scored 513, 512, 516 and 514 out of 600, that is 85.33% to
86.00%, a spread of 0.67 points between runs that differ in nothing at all.

## Conditions

| | |
|---|---|
| Model | Qwen3.6-35B-A3B, NVFP4 build, revision `491c2f1e` |
| Weights | byte-identical on both nodes: per-file sha256 manifests hash to `c4b017ad` on each |
| Server | vLLM nightly, build commit `a346d589`, image ID `a720df3e84a8` loaded on both nodes |
| Hardware | two GB10 (DGX Spark class) nodes, one GPU each, tensor-parallel 1 |
| Benchmark | MMLU, `all` / `test`, shuffled with seed 0, first 600 items |
| Item set | identical in every arm, sha256 `c074b59b` |
| Decoding | greedy: temperature 0, top_p 1, max_tokens 16 |
| Prompt | single-letter answer instruction, thinking off via chat template kwarg |
| Concurrency | 1 request in flight, so batch composition cannot vary between arms |
| Prefix caching | off, deliberately (below) |

Integrity across all six arms: **0 errors, 0 unparsable outputs**, and
truncation of 0/600 in five arms and 1/600 (0.17%) in one. The worst arm is
therefore 0.17%, comfortably inside
[trap 36](../traps/evaluation/36-token-cap-is-an-arm-level-handicap.md)'s
requirement that truncation stay under 2%. Nothing here is a token-cap
artifact.

**Prefix caching was disabled on purpose, and the production lane runs with it
on.** With it enabled, a second pass over identical prompts is served from
cache and reports a flattering agreement that measures the cache rather than
the model. Every other argument matches the live lane exactly. The floor below
is therefore conservative for the repeated-identical-query case and correct for
the case that actually matters, where the two arms differ.

## The calibration

> On this serving stack, an MMLU-style paired delta below about **1.3 points at
> n=600** is not distinguishable from re-running the same configuration.

That band is the 95% interval implied by the observed disagreement counts
(roughly `1.96 * sqrt(n_disagree) / n`, which lands at 1.27 to 1.35 points
across the six pairs). We observed a maximum of 0.67 points between identical
configurations, and 1.00 point once the MTP-off diagnostic pair is included.
Below the band, report the result as null or raise n.

## Where this floor does NOT apply

This is the part most likely to be misread, including by us, so it is stated
flatly.

**The 1.3 point band is specific to MMLU-style, single-letter, greedy,
generation-scored comparisons of this checkpoint on this build.** It is a
continuous accuracy delta over 600 four-way multiple-choice items.

**It does not transfer to binary-outcome results.** Results of the form "the
behaviour fired 10/10 times under one condition and 0/10 under another", or
"1/40 against 15/40", are a different outcome measure with their own, much
wider, binomial noise, and that noise is already what governs their
significance. Those results sit far outside this band and are neither
supported nor threatened by it. Do not quote "1.3 points" at a firing-rate
count; the two numbers are not commensurable, and applying an MMLU accuracy
floor to a 40-item binary proportion would be a category error in both
directions, too permissive for some claims and far too strict for others.

Likewise: one model, one build, one benchmark, one hardware class, one node
pair. Three cross-machine pairs from a single pair of nodes is enough to say
machine identity is not a large effect here, and not enough to bound it
tightly across a fleet.

## Relation to trap 35

[Trap 35](../traps/evaluation/35-identical-weights-do-not-score-identically.md)
recorded this class from
[@Hikari_07_jp](https://github.com/hikarioyama/qwen36-a6b)'s measurement of
98.7% cross-machine agreement on a bf16 HF transformers stack. Our
cross-machine pairs come in at 97.17%, 97.83% and 98.33%: the same phenomenon,
the same order of magnitude, slightly worse on a quantized vLLM path.

The trap reproduces here, and it generalises in a direction his framing does
not require: **you do not need two machines.** One process, scored twice, is
enough. His operating rule (designate one evaluation machine and run every arm
of a comparison on it serially) remains correct and is still the right default,
but it should not be read as sufficient. A single machine running arms serially
still has a floor, and on this stack it is the same floor.

## Reproducing

Everything needed is in
[`2026-07-28-agreement-floor-data/`](2026-07-28-agreement-floor-data/).

`raw/` holds all six answer sheets, one JSON object per item, with the raw
content and the finish reason. `scripts/build_items.py` fixes the item set (the
source, shuffle seed and slice are recorded in the file, written before any run,
so the selection cannot drift to fit a result). `scripts/runner.py` is the
serial scorer.

`scripts/verify_numbers.py` re-derives every number in this note straight from
`raw/`, with the answer extraction and the arithmetic written separately from
the original scorer so that a bug in one would not reproduce in the other. It
takes no arguments and resolves `../raw` relative to itself:

```
python3 scripts/verify_numbers.py
```

Each of its eight checks prints MATCH or MISMATCH against the figures published
above. Two defects in an earlier draft of this note were caught exactly that
way: a blanket claim of 0.00% truncation when one arm had a single truncated
item, and a discordant-count list that gave four of the six pairs. Both are
corrected above.

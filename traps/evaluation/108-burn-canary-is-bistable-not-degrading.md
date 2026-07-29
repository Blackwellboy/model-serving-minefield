# Trap 108: a fixed-seed temperature-0 burn canary settles into two outputs and alternates between them, so a consecutive-pair detector reports repeated degradation that is not happening

**Found by Blackwellboy.**

**Status: measured here, raw not published** (25 in-band canary samples over
13.009 h on one process; raw JSONL held in a staging tree).

**Symptom.** You add a burn detector to a long soak: one fixed prompt,
`temperature=0`, a fixed seed, a fixed `max_tokens`, fired on a wall-clock
cadence. Identical input, so any change in the output is the serve changing.
Partway through the run the output changes. Later it changes back. Then it
changes again. If your detector compares each sample to the previous one, it
fires every time.

Over 13 hours, 25 in-band samples produced **exactly 2 distinct outputs**:

| sha256 prefix | chars | occurrences |
|---|---|---|
| `7e776e9bd5e2` | 356 | 21 |
| `81a6298f36c3` | 346 | 4 |

The observed sequence, one character per sample:

```
A A A B B A A A B A A A A B A A A A A A A A A A A
```

**Six transitions across 24 consecutive comparisons.** A detector that alarms on
"output differs from previous sample" fires 6 times in a clean run. Not one of
the six is degradation: the series returns to `A` after every excursion, ends on
`A`, and `B` is 10 characters shorter rather than truncated, malformed or
looping. Both outputs stop of their own accord (`finish_reason: stop`).

**Mechanism.** Temperature 0 with a fixed seed does not guarantee a unique
output on this serving path. Small nondeterminism in reduction order flips a
near-tie early in the generation, and because the rest of the output is
conditioned on that token the response settles into one of a small number of
attractor completions. The set is small (2 here) and stable: no third in-band
output appeared in 25 samples across half a day.

That makes the *series* well-behaved and the *pairwise difference* meaningless.
Degradation has a direction: progressive shortening, a one-way transition, an
increasing rate of malformation. Bistable alternation has none, and the two are
trivially separable if you look at the whole series and not at adjacent pairs.

Note what the canary is still good for. It did its job: 25 samples, 2 outputs,
no third, no drift in length, TTFT locked at 0.35 to 0.37 s for every in-band
sample. That is a strong stability result. The defect is in the comparison rule,
not the instrument.

**Stacks and builds bitten.** vLLM 0.20.0, NVIDIA Nemotron 3 Super 120B A12B
NVFP4, revision `4f0cf9daaeb7a4d5e23f80a00e7ed15f0e03caf6`, single GB10-class
node, TP=1, MTP `num_speculative_tokens=3`, `--async-scheduling`,
`enable_prefix_caching=False`. Canary sent at `temperature=0`, `seed=20260728`,
`max_tokens=512`, thinking off, one request at a time with no other generation
traffic on the lane.

Two conditions worth stating because they remove the obvious explanations:
prefix caching was **off** in this configuration, so the prefix cache is not the
mechanism here; and the driver was strictly sequential, so this is
**concurrency 1**. That is the uncomfortable part. Trap
[94](../runtime/94-temp0-reproducibility-is-architecture-dependent.md)
measured concurrency 1 as reproducible in 512/512 responses, on llama.cpp on two
consumer GPUs. This is a different stack, a different architecture and a
different decode path (speculative), and it is not reproducible at concurrency 1.
The two are not in conflict, but anyone carrying "serialise the lane and you get
exactness" across from trap 94 should know it did not hold here.

A 26th sample exists and is deliberately excluded from the series above: an
out-of-band reference fired at t~0, which produced a **third** output (426 chars,
`2f97d795fd1d`) and a TTFT of 1.72 s against 0.35 s for every later sample. It
is recorded separately as `OUT_OF_BAND_T0_REFERENCE` rather than merged, because
a first request on a freshly warmed engine is not the same condition as the rest
of the series and pooling it would inflate the distinct-output count from 2 to 3.

**The check.** Score the canary on the series, never on the adjacent pair.

```python
sigs = [row["sha256"] for row in canary_samples] # in-band only
distinct = len(set(sigs))
transitions= sum(1 for a, b in zip(sigs, sigs[1:]) if a != b)
returns = sum(1 for a, b in zip(sigs, sigs[1:]) if a != b and b in sigs[:sigs.index(a)+1])

# bistable-and-clean: few distinct outputs, and the series comes back
if distinct <= 3 and returns > 0:
    print("BISTABLE, not degrading:", distinct, "outputs,", transitions, "transitions")
# degrading: monotone in a scored dimension, and it never returns
lengths = [row["chars"] for row in canary_samples]
if all(x >= y for x, y in zip(lengths, lengths[1:])):
    print("MONOTONE SHORTENING: candidate burn, investigate")
```

The operative condition is **does the series return**. One excursion that never
comes back is a signal. Six that all come back is a distribution.

**The fix.** Three things, in order of value.

1. **Alarm on the set, not the diff.** Maintain the set of distinct outputs seen.
   Fire when a *new* member appears late in a run, or when the set stops
   containing the original output, not when consecutive samples differ.
2. **Score a dimension that has a direction.** Length, extractability, and
   malformation rate all degrade one way. Output identity does not.
3. **Do not assume `temperature=0` plus a seed gives you one string.** Measure
   the size of the attractor set on your own lane before treating any canary
   verdict as exact-match. Two requests establish whether you are in this regime;
   twenty-five establish the set size.

**Found.** 2026-07-28, in a 13-hour production soak, where the detector fired six
times and every firing was investigated and discarded.

**Attribution.** Blackwellboy.

## Scope

25 in-band samples on one prompt, one process, one node, one day. The set size of
2 is a property of this prompt on this lane and does not transfer: a different
prompt has a different number of near-ties and may have one output or five. What
transfers is the shape of the error, which is the pairwise comparison rule, and
that is stack-independent.

Related: trap [94](../runtime/94-temp0-reproducibility-is-architecture-dependent.md)
(temperature-0 reproducibility is architecture dependent) and trap
[35](35-identical-weights-do-not-score-identically.md)
(the harness-level consequence). This entry is the monitoring-level consequence:
the same nondeterminism, met by a detector rather than by a scorer.

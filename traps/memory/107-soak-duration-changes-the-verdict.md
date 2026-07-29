# Trap 107: a short soak reports a memory leak and a throughput decline that a long soak on the same process shows do not exist

**Found by Blackwellboy.**

**Status: measured here, raw not published** (13.009 h single-process soak,
2,045 turns, 147 instrumented scrapes; raw JSONL held in a staging tree).

**Symptom.** You soak a serve for a few hours, plot container memory, and it
rises monotonically. Every sample is at or above the one before it. You compute
a rate, extrapolate, and write down a leak. Separately your decode rate is
drifting down across run quartiles, monotonically, in the same run. Both series
look like textbook degradation and neither is.

At 5.4 hours into one process, container memory had gone
3.217 to 3.448 GiB across 13 consecutive non-decreasing samples, about
0.043 GiB/h. At 8.0 hours the decode-rate quartile medians were
27.666, 27.634, 27.504, 27.434 tok/s: monotone down, about -0.86%.

Neither survived the full run:

| Series | Read at 5.4 h | Read at 9.2 h | Read at 13.0 h |
|---|---|---|---|
| container memory | monotone rise, ~0.043 GiB/h | plateaued | bounded transient, **fully reverted** |
| decode rate | (still oscillating) | (still oscillating) | **not monotone**, Q3 is the maximum |

Memory peaked at **3.538 GiB at h=7.36**, then fell to **3.354 GiB at h=13.0**,
which is *below* its own h=1.09 value of 3.378 GiB. Total excursion 0.32 GiB,
fully recovered. Host available memory ended higher than it started
(3,990 to 4,578 MB). Preemptions were 0 at every one of the 147 scrapes. The
final decode quartiles were 27.578, 27.621, 27.691, 27.459 tok/s: the middle of
the run is the fastest part, so there is no slope to report.

**Mechanism.** Nothing in the serve was degrading. A bounded allocator or
page-cache excursion, entered and then released, presents as a monotone series
for as long as your observation window sits inside its rising limb. Monotonicity
is not a property of the process; it is a property of the window you happened to
choose. Any strictly increasing sample of a hump looks exactly like the
increasing limb of an unbounded curve, and the two are indistinguishable from
inside the window. The same holds for a quartile trend computed over a run that
has not finished: four quartiles of an oscillating series will be monotone by
chance a meaningful fraction of the time, and there were four consecutive
non-decreasing samples in this run's memory series that meant nothing.

The failure is not that the short reading was sloppy. It was correct about its
own data. The failure is that "monotone across every sample I have" was treated
as a shape when it was a window artifact.

**Stacks and builds bitten.** vLLM 0.20.0 (image digest
`sha256:04563c302537a91aa49ebdfbceda96111c5712275999b7e8804fa598f0b5641d`),
NVIDIA Nemotron 3 Super 120B A12B NVFP4, revision
`4f0cf9daaeb7a4d5e23f80a00e7ed15f0e03caf6`, single GB10-class node, TP=1,
MTP `num_speculative_tokens=3`, `--gpu-memory-utilization 0.90`,
`--max-num-seqs 4`, `enable_prefix_caching=False`. Sequential single-stream
load, seven interleaved task families, 2,045 turns.

This produced a published number in the sense that matters: an intermediate
report from this run stated the leak rate and its 30-day extrapolation
(+31 GiB) before the run was long enough to contradict it. It was withdrawn at
9.2 h and again at 13.0 h. Nothing reached the registry, because the run
outlived the reading.

**The check.** Two assertions, both cheap, both runnable against your own soak
without our data.

1. **Never report a trend from a series that has not turned over.** Before
   quoting a rate, assert that the series has at least one local maximum and one
   local minimum inside the window, or say explicitly that it has not:

   ```python
   xs = [row["mem_gib"] for row in scrapes]
   turned = any(xs[i-1] < xs[i] > xs[i+1] for i in range(1, len(xs)-1)) and \
            any(xs[i-1] > xs[i] < xs[i+1] for i in range(1, len(xs)-1))
   if not turned:
       print("NO TURNOVER: monotone-so-far. Do not quote a rate or extrapolate.")
   ```

2. **Extrapolate only across a horizon you have actually observed a turnover
   in.** A rate measured over 5 hours licenses a statement about 5 hours. The
   30-day figure was the tell: it was the only claim in that report whose
   horizon exceeded its evidence by three orders of magnitude.

A third, weaker check that would also have caught it: a monotone series with a
flat neighbour is suspicious. Host available memory was flat to noise
(4,347 to 4,425 MB) across the same window in which container memory was
"leaking", and 0.32 GiB against a 121 GiB pool is not a quantity that could move
the host figure. When one memory series drifts and the one it must be drawn from
does not, the drift is more likely to be in the accounting than in the machine.

**The fix.** Set the soak length from the shape you need to resolve, not from
convenience. If the question is "does this leak", the run has to be long enough
for a bounded excursion to come back, and there is no way to know that length in
advance except by running past the first plateau. Where that is unaffordable,
the honest output is "monotone over N hours, no turnover observed, no rate
quoted", which is a real result and is not the same as "no leak".

Flag weak extrapolations rather than acting on them. The reason this was caught
at all is that the 5.4 h report named the 30-day figure as the weakest claim it
was making, so there was something specific for the longer run to kill.

**Found.** 2026-07-28, during the first long-duration soak of this checkpoint.
The soak was run to characterise speculative-decoding acceptance drift; the
memory series was secondary instrumentation and turned out to be the finding.

**Attribution.** Blackwellboy.

## Scope, and what this does not say

Single serve, no baseline arm, one node, one process, one day. Nothing here is
comparative and nothing establishes run-to-run variance. It does not say that
serving stacks do not leak, and it is not evidence that this checkpoint has no
leak on a longer horizon than 13 hours: the entry's own argument forbids that
reading. What is established is that a monotone series over hours resolved to a
transient over half a day, on one real process, with the intermediate readings
recorded as they were made.

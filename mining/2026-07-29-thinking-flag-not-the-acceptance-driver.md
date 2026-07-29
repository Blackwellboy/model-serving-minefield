# Candidate: the thinking flag is not the driver of speculative acceptance on this build

**Mining candidate. Held back from `traps/` as too thin, and its cross-run
framing does not survive checking.**

## The observation

On the DSV4 abliterated build, two families ran **identical prompts** differing
only in the thinking flag:

| family | acceptance |
|---|---|
| math_nothink | 78.14% |
| math_think | 74.80% |

**Delta -3.34 points**, against a **34.78-point** spread across the six families
in the same run. On this build the task moves acceptance and the reasoning toggle
barely does.

The comparison is unusually clean: the two arms share prompts, so this is a
paired contrast rather than two families that happen to differ. That is the
strongest thing about it.

## Why it is not an entry yet

1. **One build, one pair, one session.** A single -3.34 pt paired delta on one
   checkpoint is a data point, not a mechanism. There is no second build, no
   replication, and no baseline arm anywhere in the run.
2. **No stated resolution.** The registry requires an accuracy or score delta to
   carry what the design could resolve. This is an acceptance rate rather than an
   accuracy score, so the 1.3 pt MDE does not transfer to it, and no
   binary-outcome floor was computed for it either. Until somebody says what
   -3.34 points can be distinguished from on this measurement, its size cannot be
   interpreted, only reported.
3. **It is a negative dressed as a finding.** "Flag X is not the driver" is
   useful context for someone tuning a lane, but it does not tell a reader what
   to do differently, and it has no check that would bite anyone.

## The cross-run framing in the source is wrong, and this is the substantive correction

The DSV4 writeup states this result "points the opposite way from the Super
result, where reasoning was the worst family."

**The Super run cannot support that comparison.** Its speculative-decoding
counters are process-wide and its workload was seven families round-robin with a
scrape every 14 turns, which is exactly two complete cycles, so every measurement
window contained all seven families in equal counts. It produced **no per-family
acceptance figures at all**, and its own writeup records that limitation
explicitly.

What the Super run actually established about the reasoning family is a
**different quantity**: reasoning was the worst family for **empty content** at a
token ceiling with thinking on (30.82% of thinking-on reasoning turns returned
blank), and it was second-slowest by **decode rate** (26.4 tok/s). Neither is
acceptance. Decode rate is driven by acceptance but also carries prompt length,
sampling and scheduler effects, and the Super analysis labels it a proxy and
explicitly declines to size the acceptance spread from it.

So the two runs are not opposed. One measured per-family acceptance and found the
thinking flag unimportant; the other measured per-family empty-content rate and
found the thinking flag decisive (0 empties in 1,022 thinking-off turns). Those
are compatible statements about different quantities, and reading them as a
conflict would put a contradiction into the registry that the data does not
contain.

## What would promote it

A second build with a paired think/nothink arm on identical prompts, plus a
stated resolution for the acceptance delta. If a second build shows a large
positive delta where this one shows -3.34, the pair becomes a real
"do not assume the thinking flag drives acceptance" entry with two points.

Cheapest path: the same paired-prompt construction on any lane already serving a
reasoning model with speculative decoding enabled. It needs no serve change.

**Found.** 2026-07-28, DSV4 long soak.

**Attribution.** Blackwellboy.

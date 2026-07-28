# Trap 55: your speedup was run order, warm caches, or cross-session drift

**Found by TheTom.**

**Status: reproduced here** (the claimed effect reproduced on a branch that did not contain the
feature, which is the disproof; raw sweeps held outside the tree; can be produced on request, per
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo)).

**Symptom.** A tuning change shows a clean **+21 to 24%** prefill improvement at 4K. It is
consistent,
it survives a re-run, and it has a plausible mechanism. Then the same improvement shows up on a
branch **without the feature**.

**Mechanism.** Three distinct artifacts, all of which look like a real effect:

1. **Run order.** The first configuration in a sweep pays for cold caches, graph capture,
   kernel-cache population, compilation, allocator warm-up. Whichever config runs *second* inherits
   the warm state and wins. Our "+21 to 24% autotune win" was cudagraph and compile caches warming
up,
   and it reproduced identically on the no-autotune branch. Cost: about $15 of GPU time to disprove
   a result we had already half-believed.
2. **Cross-session baseline drift.** A separate change "measured" a 10 to 16% regression that turned
   out to be drift between sessions, not the change. Comparing today's A against yesterday's B is
   not a comparison.
3. **Peak versus trend.** A memory reading spiking to 50 GB looked like an unbounded leak; it was a
   command-buffer high-water mark that dropped back between requests. The real leaks were elsewhere.
   Distinguish `metric(t)` **peak** from `metric(t)` **trend** before chasing either.

The common root: **the thing you varied was not the only thing that varied.**

**Stacks and builds bitten.** Seen on GPU stacks with graph capture and JIT compilation
(torch.compile
plus CUDA graphs) and on Metal. Anything with a warm-up phase, which is now everything.

**The check.**

1. **Counterbalance the order.** Run A to B and B to A and compare. If the winner is whichever ran
second,
   you have this trap and no result.
2. **Discard warm-up explicitly.** Fixed warm-up count (we use at least 8 steps), then an N-run
median. Then
   check that the *warmed* runs are stable, monotonic degradation across warmed runs is thermal
   throttling, a different artifact with the same shape.
3. **Test the null.** Run the "improved" configuration on a build that does not contain the
   improvement. This is the cheapest disproof available and it is the one that settled ours. If the
   effect survives, it was never your feature.
4. **Never compare across sessions.** Re-measure the baseline in the same session, on the same
   binary, with the same clocks locked. Record the build hash and the locked clock with every
number.
5. **Lock clocks.** Demand-governed boards swing widely, one dev board ranged 363 to 597 MHz, and a
   figure that had been quoted for weeks was simply a high-clock sample about 20% above the locked
   baseline.

**The fix.** Treat any unpaired, un-counterbalanced measurement as a hypothesis. A result is a
result when it survives order reversal, a fresh baseline in the same session, and a null-build run.

Practical framing that has saved us repeatedly: **an outsized improvement is a bug report until
proven otherwise.** If the number moved more than the change plausibly explains, the likely
explanations are, in order: a measurement artifact (this trap), a correctness regression that
removed
work ([trap 53](53-speed-measured-on-a-broken-config.md)), and only then a real win.

**Found.** 2026-05 and 2026-06, across two separate optimization arcs that each produced a
published-adjacent number before being disproven.

**Attribution.** TheTom.


# Trap 54: your speedup was run order, warm caches, or cross-session drift

**Found by TheTom.**

**Status: contributor-measured, conditions as reported.** That is the label for everything this entry is about. A second, narrower claim inside it is separately reproduced here, on a different experiment, and the two are scoped per claim below rather than blended, because a skimmer should not carry the stronger label onto the wrong one.

| Claim | Status |
|---|---|
| Run order, warm caches and cross-session drift produce a clean, reproducible, false speedup. The +21 to 24% prefill result, the null-build disproof, the cudagraph and clock effects. **This is what the entry is about.** | **contributor-measured, conditions as reported** (TheTom, on his own hardware; conditions below, raw private) |
| The framing rule the entry is built on: an outsized headline number is a bug report until proven otherwise | **reproduced here**, but on a different experiment. Another lab's +2.64 point coding-benchmark effect fell to -1.02 under a temperature-controlled re-run while its secondary flakiness claim survived. Raw, drivers and per-sample JSONL: [laguna-s21-lab/pr10-replication](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/pr10-replication) |

**Read the second row narrowly.** "Reproduced here" attaches to the framing
rule, **not** to this entry's prefill story and not to any of its mechanisms.
Our controlled variable was temperature parity, not run order or cache state;
we controlled order by interleaving rather than by the counterbalancing this
entry prescribes; and we have never run the null-build disproof, measured a
warm-cache or cudagraph warm-up effect, or locked clocks. Every mechanism below
is contributor-measured and none of it has been reproduced here.

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

**A concrete, default-on instance of this, found independently by two other people.**
@apollo-mg reported that llama.cpp output at temperature 0 depends on server state, and that one of
the three channels he found is **on by default**: `cache_prompt = true`. The same request, freshly
prefilled from a 4,704-token prompt, returns one hash stably; served from a 30-token warm prefix it
returns a different one. No restart, no concurrency, stock flags. He has concurrent batched decoding
as a separate channel, reproducing on upstream at `0e4a036`.
[report](https://github.com/TheTom/offlabel/pull/10#issuecomment-5099416581)

@Defilan then ran the same check on a third stack, Laguna S 2.1 on llama.cpp Vulkan / gfx1151,
single slot, temp 0, with `cache_prompt: false` set on every request. Cold was deterministic across
three runs; warm diverged anyway, so on that stack the flag did not fully isolate an identical
request from what was in the slot before it. He is explicit that n=3 makes it an existence proof
rather than a rate, and that he has not identified the mechanism.
[report](https://github.com/TheTom/offlabel/pull/10#issuecomment-5099697368)

Neither had read this entry. Two stacks neither of them shares with the other, and neither with
this entry's author. Credit for both is theirs.

**What that sharpens, past counterbalancing.** A protocol should state its **prefix-reuse and
concurrency settings the way it states temperature**, because on these stacks they are as
determinative and they are not neutral by default. And where this reproduces, **flushing the slot
between samples is worth more than trusting the flag**: @Defilan's run is the case where setting
`cache_prompt: false` was not sufficient on its own.

**The fix.** Treat any unpaired, un-counterbalanced measurement as a hypothesis. A result is a
result when it survives order reversal, a fresh baseline in the same session, and a null-build run.

Practical framing that has saved us repeatedly: **an outsized improvement is a bug report until
proven otherwise.** If the number moved more than the change plausibly explains, the likely
explanations are, in order: a measurement artifact (this trap), a correctness regression that
removed
work ([trap 52](52-speed-measured-on-a-broken-config.md)), and only then a real win.

**Found.** 2026-05 and 2026-06, across two separate optimization arcs that each produced a
published-adjacent number before being disproven.

**Attribution.** TheTom.


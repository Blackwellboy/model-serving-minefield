# Trap 52: the fast configuration was fast because it was wrong

**Found by TheTom.**

**Status: contributor-measured, conditions as reported.** Measured by the contributor on their own hardware; conditions are stated in the entry. Not independently reproduced here. Raw is private and available to maintainers on request, which is why this is not 'reproduced here' (see [CONTRIBUTING](../../CONTRIBUTING.md#status-vocabulary)).

**Symptom.** A configuration hits an impressive throughput number and you write it down. It is
reproducible, stable across runs, and sits exactly where you hoped parity would be. Weeks later the
correctness gate lands and the number evaporates, because the fast path was skipping the work.

Concretely: **77.7 tok/s "speed parity" turned out to be the model producing garbage fast**, because
the dequantization path was missing its rotation step. Every speed number we had recorded above
**10.7 tok/s** was invalid, across an entire optimization arc.

**Mechanism.** Correctness and throughput are measured by different harnesses, and the throughput
harness does not care what the tokens say. Any optimization that *removes* required work makes the
number better and the model worse: a skipped inverse rotation, a dropped normalization, an
unapplied scale, a reduction that loses terms. Nothing errors, because nothing checks.

It is worse than an ordinary bug because the incentive gradient points the wrong way: the broken
config is the one that "wins", so it survives review, gets promoted to the default, and becomes the
baseline that later correct work is measured against.

The same shape shows up in three other forms we hit:

- A **coherent but wrong** model. An output that reads fine while the correct answer sits at
  **rank 1213**: produced by a reduction tree that silently dropped a third of its terms at a
  non-power-of-two threadgroup size. Readability is not correctness.
- A **quality claim in a stale docstring.** "3-bit +20.59% perplexity" turned out to be 10 to 30x
  pessimistic against measurement on the current path. Numbers rot; re-measure before quoting your
  own repo.
- **Speed parity between architecturally different things.** A checkpoint whose branding implies
  ~2B effective parameters served with an on-disk parameter count of ~4.65B. The tok/s comparison
  against a true 2B is not the comparison you think.

**Stacks and builds bitten.** Ours was a Metal quantized-matmul path on Apple silicon, but nothing
here is stack-specific, it is a harness-design trap. Any engine where the perf bench and the
correctness bench are separate commands can produce it.

**The check.** **Gate every performance number on a correctness assertion produced by the same
binary, same flags, same session.** Not a correctness run from last week on a different build.

Minimum viable gate, in order of cost:

1. A coherence probe plus a **discriminative** probe, capital-of-France catches gross breakage, a
   decimal comparison (`9.9` vs `9.11`) catches subtle breakage that the first one passes. See
2. **Top-1 rank of a known answer**, not just readability of the output. Rank 1213 for "Paris" reads
   as fluent text.
3. Perplexity or KL against a high-precision reference on the same build, if the change touches
   numerics at all.

Then record the correctness result *in the same row as the throughput number*. A perf table with no
correctness column is an invitation to this trap.

**The fix.** Refuse to record a tok/s figure that has no correctness artifact attached to it. When a
number improves by more than the change plausibly explains, treat that as a **correctness alarm**
first and a win second, the outsized speedup is the tell.

Corollary for reviewers: "it got faster and nothing broke" is not a report. "It got faster and here
is the probe output from the same build" is.

**Found.** 2026-03, discovered when a rotation-in-dequant correctness fix collapsed a number that
had
already been quoted.

**Attribution.** TheTom.

**Check script.** The runnable version of this check is in review separately: every check in this repo must declare the negative and empty-set controls described in [the check contract](../../checks/README.md), and this one does not yet. The assertion above is the check; the script is a convenience wrapper for it.

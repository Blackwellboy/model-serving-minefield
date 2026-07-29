# Candidate: an SDPA block-count tuning knob silently drops attention mass

**Raised by TheTom. Status: under test.** Not promoted, it is a specific upstream kernel detail we
worked around rather than a serving trap we have measured end-to-end quality damage from.

**Claim.** A two-pass SDPA vector kernel reduces its partial results with
`for b in 0..blocks/BN` at `BN = 32`. Integer truncation means that when `blocks % 32 != 0`, the
remainder partials are **never accumulated**: attention mass is silently lost. A tuning example
circulating with a non-multiple-of-32 block count (`88`) "works" only because the resulting mass loss
is small enough not to be obvious in generated text.

**Why it belongs in the registry if it holds.** It is a knob a user is invited to tune, it has no
guard, and the failure is *quiet degradation* rather than an error, the hardest class to attribute.
Anyone sweeping that knob for throughput would be trading unmeasured accuracy for it and would have
no way to tell from the output.

**Practical rule we adopted.** Only use block counts that are multiples of 32, {32, 64, 96, 128,
160, 256, 512, 1024}. And in our own DSL work, the generalized version: **use `ceil_div`, never
integer truncation, in any multi-block reducer, and bound-check the inner loop with `idx < blocks`.**

**What would settle it.** Quantify the damage rather than assuming it: run a fixed prompt set at a
multiple-of-32 block count and at a non-multiple (e.g. 88), and measure top-1 agreement, KL against
the multiple-of-32 run, and perplexity, on the same build, same session. If the divergence is
measurable at realistic settings, this is a full entry; if it is genuinely negligible, the correct
outcome is an upstream note rather than a trap.

Second open question: whether current upstream still has the truncating loop, or whether it has since
been guarded. Should be checked against the current source before this is promoted or dropped.

**Attribution.** The kernel is upstream; the multiple-of-32 rule and the `ceil_div` generalization
are ours. Not independently attributing the original tuning example to its author, since the point
here is the kernel behavior rather than anyone's usage of it.

---

## Maintainer adjudication, 2026-07-29

**Accepted as a mining candidate, GATED ON SOURCE VERIFICATION.** Everything
above this line is TheTom's text as submitted in PR
[#1](https://github.com/Blackwellboy/model-serving-minefield/pull/1) and is
unedited. This section is ours.

**His second open question is the right first step, and it is cheaper than the
one he listed first.** He proposed quantifying the damage (top-1 agreement, KL,
perplexity at a multiple-of-32 block count versus 88). Before any of that:

> **Does current upstream still carry the truncating loop, or has it since been
> guarded to handle partial blocks?**

Until that is answered against **current** source, quantifying the damage may
be measuring a bug that is already fixed, and a measured divergence would be
attributed to a defect that no longer exists. So the quality measurement is
explicitly **not** the next action here, and no damage figure should be
published ahead of the source read.

**We have not made that source read.** Nothing in this note asserts the state
of current upstream in either direction.

**Conditional routing, decided in advance so the result is not adjudicated
after the fact.** If the source read shows the truncating loop is still
present, this is most likely an **upstream-reported / kernel-implementation
item** rather than an operator-controlled serving trap: it is a kernel detail,
and the registry's `traps/` tier is for things a serving operator configures.
A block-count tuning knob is closer to the line than most, which is why the
routing is written down rather than left to taste. If the loop has been
guarded, the correct outcome is a closed candidate with the fix linked.

**The durable payload survives either outcome**, and it is his:

> Use `ceil_div`, never integer truncation, in any multi-block reducer, and
> bound-check the inner loop with `idx < blocks`.

That is an implementation lesson that holds independently of this kernel's
current state, and it is the part worth keeping if the specific instance
closes.

**Not promoted to a numbered trap**, pending the source read above.

**Credit.** The candidate, the multiple-of-32 rule and the `ceil_div`
generalisation are TheTom's. The kernel is upstream, and he declined to
attribute the original tuning example to any individual, which we have left
as he wrote it.

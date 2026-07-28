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

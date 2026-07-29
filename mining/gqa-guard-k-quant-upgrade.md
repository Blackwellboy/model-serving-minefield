# Candidate: a KV-quant safety guard silently costs a third of the context ceiling

**Raised by TheTom. Status: reported by others, consistent with our own data.** Not promoted ,
the finding comes from an independent reimplementation's triage, and the guard is specific to one
fork rather than to an engine everyone runs.

**Claim.** A KV-quant fork auto-upgrades the K cache from its 3-bit codec to `q8_0` whenever the
GQA ratio is at or above 6. On at least one architecture that guard is over-conservative, and the
cost is not quality, it is **context ceiling**.

**What we have.**

- The guard was calibrated on a 7:1 GQA architecture where 3-bit K was genuinely catastrophic
  (perplexity 2887). That calibration is sound and should stay.
- On a 6:1 model with 256-dim heads, an independent reimplementation's wikitext triage found
  symmetric 3-bit K+V costs **+0.87%** perplexity, and **K alone costs +0.17%**: while the guard
  costs **33% of the context ceiling** (98K vs 131K on a 24 GB card).
- Proposed mechanism: 256-dim heads decompose into two independent 128-wide rotation groups, which
  apparently carries K acceptably at 6:1. Plausible, not proven.
- Our own cross-validation of that reimplementation passed every other gate, bitwise codec match,
  full kernel suite, byte-exact canonical CLI output, so the source is credible.

**Why it belongs in the registry eventually.** The generalizable trap is not this specific guard,
it is: **a safety guard silently changes your effective config, and the flag you passed is not the
config you got.** Log the *effective* per-tensor KV type at runtime, not the flag. That rule applies
to every engine.

**What would settle it.** Per-architecture calibration data: perplexity and context ceiling at
symmetric 3-bit K+V vs the guarded config, across at least three architectures spanning GQA ratios
4:1 through 8:1 and both 128- and 256-dim heads. If the head-dimension hypothesis holds, the guard
should key on head dim as well as GQA ratio, or expose a user override.

**Attribution.** The triage and the numbers belong to the independent reimplementation's author;
the cross-validation and the effective-config framing are ours.

---

## Maintainer adjudication, 2026-07-29

**Accepted as a mining candidate.** Everything above this line is TheTom's text
as submitted in PR
[#1](https://github.com/Blackwellboy/model-serving-minefield/pull/1) and is
unedited. This section is ours.

**The framing is the part we want, and it is the durable payload:**

> A safety guard silently changes your effective config, and the flag you
> passed is not the config you got. Log the **effective** per-tensor KV type at
> runtime, and verify it there. Do not infer it from the flag you requested.

That is trap
[10](../traps/quantization/10-quant-label-is-not-the-kernel-path.md)'s lesson
on a new lever. Trap 10 is about a quantisation label not determining the
kernel path actually taken; this is a guard rewriting a per-tensor type after
the request. Same class, different mechanism, and it is a promotion candidate
on its own merits regardless of whether the specific 6:1 guard turns out to be
over-conservative.

**The specific attribution stays unverified.** The 6:1 GQA / 256-dim-head
claim, the +0.87% and +0.17% perplexity figures, and the 33% context-ceiling
cost are the independent reimplementation's numbers, not ours. We have not
reproduced them and we cannot: **we have no fork lane at 6:1 with 256-dim
heads.** The head-dimension mechanism above is explicitly labelled plausible
rather than proven by its own author, and we are not upgrading that label.

**Promotion gate: the per-architecture calibration TheTom specified**, across
at least three architectures spanning GQA 4:1 to 8:1 and both 128- and 256-dim
heads. We cannot supply it, so this stays a candidate until someone with those
lanes runs it.

**Not generalised beyond the evidence and not promoted to a numbered trap.**
The effective-config rule is stated as a rule; the specific guard is stated as
one reimplementation's triage on one architecture.

**Credit.** The candidate, the triage sourcing and the effective-config framing
are TheTom's. The numbers belong to the independent reimplementation's author,
as he recorded.

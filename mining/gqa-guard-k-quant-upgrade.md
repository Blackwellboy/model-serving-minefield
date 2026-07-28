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

# Trap 111: two clean suites, same config, same prompts, medians 20% apart: greedy decode resamples your content, and acceptance prices it

**Found by Blackwellboy.**

**Status: measured here, raw not published.** Both suites ran on our lane on
2026-08-03, interference-screened per
[trap 110](110-unscreened-bench-on-a-shared-endpoint.md), and the raw is not
shipped. The mechanism rests on two things a stranger can verify
independently: greedy non-reproducibility across sessions (documented with
shipped raw in
[the agreement-floor note](../../mining/2026-07-28-our-agreement-floor-greedy-not-reproducible.md))
and the acceptance-throughput coupling below, which any speculative lane's
own `/metrics` will reproduce in an afternoon.

**Symptom.** A speculative-decoding lane benchmarked twice in one day, same
checkpoint, same launch line, same twelve prompts, both suites clean under
interference screening, returns median 242.5 / mean 232.7 tok/s in one
session and median 199.9 / mean 220.2 in the other. Neither run is wrong and
nothing changed. If the two had been different configs, the 20% gap would
have been read as a real effect and published.

**Mechanism, in two coupled halves.**

First, temperature-0 decode is not reproducible across sessions. Greedy
tie-breaks land differently between server restarts and even between
batches, the divergence compounds token by token, and two sessions generate
genuinely different text from the same prompts. That much is general (see
the agreement-floor note, and
[trap 94](../runtime/94-temp0-reproducibility-is-architecture-dependent.md)
for how architecture-dependent the guarantee is).

Second, on a speculative lane, throughput is a function of the text being
generated. Draft acceptance depends on how predictable the content is, and
decode speed tracks acceptance nearly linearly: on this lane, a prompt whose
generation accepts 2.8 tokens per step decodes at about 168 tok/s and one
that accepts 5.6 decodes at about 302, a 1.8x spread inside one clean suite
(per-position acceptance 0.85 / 0.66 / 0.55 / 0.37 / 0.19). Compose the two
halves: greedy resamples which text you get, acceptance prices the text, and
the suite median inherits the lottery. A non-speculative lane hides the
first half because every generation runs at the same speed; speculation
converts content divergence into throughput variance.

**Stacks and builds bitten.** A vLLM-derived build serving
[Rarri/DeepSeek-V4-Flash-0731-NVFP4](https://huggingface.co/Rarri/DeepSeek-V4-Flash-0731-NVFP4)
with MTP speculative decoding at fixed depth 5, greedy draft sampling,
tensor parallel 2 on 2x RTX PRO 6000 Blackwell. The mechanism applies to any
speculative lane benchmarked at temperature 0 across sessions.

**The check.** Run your single-stream suite twice with a server restart
between. If the medians differ by more than your claimed effect size, your
claimed effect is not measurable that way. Log acceptance length per run
from `/metrics` deltas next to every throughput number; if throughput and
acceptance move together across your two runs, you are looking at this trap
and not at drift, thermals or contention.

**The fix.** Three rules, all cheap:

1. Publish the range and the acceptance profile next to any speculative
   median. "199.9 median, 167 to 302 observed, mean acceptance 3.85 of 6"
   is a reproducible claim; "199.9 tok/s" alone is a coin flip.
2. A/B configurations inside one session on fixed prompts, never across
   sessions. Cross-session deltas below about 20% on this lane are noise.
3. Treat suite size as a variance decision: twelve prompts was enough to
   see the 167 to 302 spread but not enough to pin the median tighter than
   about 20%.

**Found.** 2026-08-03. The two suites were run to confirm a tuning win and
disagreed with each other by more than the win.

**Attribution.** Blackwellboy.

**Related.**
[Trap 110](110-unscreened-bench-on-a-shared-endpoint.md) (screen first; this
entry is about the variance that survives screening),
[trap 94](../runtime/94-temp0-reproducibility-is-architecture-dependent.md)
(temperature 0 is not a reproducibility guarantee),
[trap 54](54-run-order-and-warm-cache-artifacts.md) (cross-session drift as
a confound class),
[trap 105](105-acceptance-estimator-unnamed.md) (which acceptance number
you are even quoting),
[trap 109](../quantization/109-requant-skips-draft-layer-experts.md) (the
lane whose recovery these suites were measuring).

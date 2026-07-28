# Candidate: `presence_penalty` sensitivity causes multi-second latency on trivial prompts

**Raised by TheTom. Status: reported by others, partially observed here.** Not promoted, we have
the symptom and a plausible named cause, but no controlled A/B of our own.

**Claim.** Some model families are unusually sensitive to `presence_penalty`; with the wrong value
the model overthinks massively, and the result is read as "this model is bloated" rather than
"this sampler config is wrong."

**What we have.**

- Reported by multiple independent operators: a 9B in one family takes **~22 seconds** to reply to
  "Hi"; a 27B in the same family shows similar behavior on trivial prompts; both get **worse when
  quantized**.
- The named cause. `presence_penalty` sensitivity in that family, comes from a single credible
  upstream source and has not been independently reproduced here with a controlled sweep.
- We have observed the symptom (multi-second latency on greetings) on that family and confirmed that
  pinning documented sampler values removes it. That is consistent with the claim but does not
  isolate `presence_penalty` from the other values we pinned at the same time.

**Why it is worth settling.** The cheap check is genuinely useful regardless of mechanism:

> **Time a trivial greeting.** Multi-second latency on "Hi" is a sampler or thinking problem, not a
> model-capability problem.

That one line has caught misconfiguration on several stacks. It just does not yet justify naming
`presence_penalty` specifically.

**What would settle it.** A one-variable sweep on a fixed trivial prompt: hold temperature, top_p,
top_k, and the thinking flag constant; vary `presence_penalty` across the plausible range; report
reasoning-token count and wall latency per value, at two quantization levels (the "worse when
quantized" part of the report is the most interesting and least verified piece).

**Adjacent, better-established.** The thinking flag itself is the larger lever for this symptom, and
that one is measured, see the thinking-ablation material: extended reasoning helps a narrow band of
axes, no-ops on several, and actively hurts execution and integrity axes at roughly 10x the token
cost.

**Attribution.** Symptom reports and the `presence_penalty` attribution belong to their original
reporters; the greeting-latency check is ours.

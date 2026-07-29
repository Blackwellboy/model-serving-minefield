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

---

## Maintainer adjudication, 2026-07-29

**Accepted as a mining candidate, with the portable payload separated from the
causal attribution.** Everything above this line is TheTom's text as submitted
in PR [#1](https://github.com/Blackwellboy/model-serving-minefield/pull/1) and
is unedited. This section is ours.

**The check lands, but it needs a second step before it licenses any
inference.** As he wrote it:

> **Time a trivial greeting.** Multi-second latency on "Hi" is not a
> model-capability problem.

That negative half is safe. The positive half is not, and this registry already
holds the counterexample: trap
[48](../traps/routing/48-dual-stack-mdns-latency-tax.md), **his own entry**,
records trivial requests taking **30 to 40 s** through an agent client while
the server's own log showed the work finishing in **1 to 10 s**. The cause was
a dead IPv6 route on an mDNS hostname, and nothing about the sampler or the
thinking config was wrong. Trap 48 also names the correct first move on **any**
unexplained latency, which is not the greeting timing:

> Compare the server's own logged total time against the client-reported
> latency for the same call. A large, roughly constant, client-only gap is not
> a model or engine problem.

So the check as stated would send an operator to read sampler and thinking
settings for what may be a network, queueing or cold-start delay. The fix is
one extra step, not a retraction:

1. **Time a trivial greeting.** Multi-second latency on "Hi" is not a
   model-capability problem. Something is wrong; this does not yet say what.
2. **Reconcile client against server timing** before concluding anything, via
   [`checks/latency_reconciliation.py`](../checks/latency_reconciliation.py) or
   the server's own request log. A large client-only gap is trap 48's class:
   transport, resolution or queueing.
3. **Only if the server's own total is itself large** does this become a
   sampler or thinking question, and then the evidence to collect is the
   **reasoning-token count** on that greeting, which distinguishes "the model
   thought for pages about Hi" from "generation was slow".

With step 2 in place the check is portable, costs two cheap reads, and has
caught real misconfiguration on several stacks including ours. Without it, it
is a symptom with three candidate causes and a prescription for one of them.

**The attribution to `presence_penalty` specifically stays UNVERIFIED**, and
this note says so rather than letting the check carry it silently. What we
have is a symptom we have seen, plus a report from elsewhere naming a cause,
plus the observation that pinning documented sampler values removes the
symptom. That last step pinned several values at once, so it cannot isolate
`presence_penalty` from the others. This is the failure mode the separation
exists to prevent: a cheap, portable, correct check quietly acquiring an
unproven mechanism because the two arrived in the same note.

**Promotion gate: the one-variable sweep TheTom specified.** Hold temperature,
top_p, top_k and the thinking flag fixed on a fixed trivial prompt; vary
`presence_penalty` across the plausible range; report reasoning-token count and
wall latency per value, at two quantisation levels. The "worse when quantised"
half of the original report is the least verified piece and the most
interesting.

**Adjacent and already covered, so it is not re-litigated here.** Sampling
parameters accepted and discarded by a serving path is
[U02](../upstream/U02-ollama-go-runner-drops-sampling-penalties.md), which is
upstream-reported and about penalties being ignored rather than harmful.
Card-recommended sampler values losing to server built-ins is trap
[21](../traps/versioning/21-no-generation-config-server-defaults-win.md). This
candidate is neither: it is about a penalty value that **is** applied and
degrades latency. Recorded so the three are not merged by a later reader.

**Not promoted to a numbered trap**, pending the sweep.

**Credit.** The candidate, the separation of check from mechanism, and the
greeting-latency check are TheTom's. The symptom reports and the
`presence_penalty` attribution belong to their original reporters, as he
recorded.

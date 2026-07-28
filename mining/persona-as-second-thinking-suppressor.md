# Candidate: a professional-identity persona suppresses thinking independently of the thinking flag

**Raised by TheTom. Status: under test.** Not promoted, the mechanism is inferred, and the
generality across families is untested.

**Claim.** A named professional-identity persona in the system prompt (`You are a senior software
engineer at ...`) materially suppresses a model's thinking-fire rate, independently of any
`enable_thinking` flag. If that holds, persona is a **second, undocumented config lever**: and one
that matters most on APIs that do not expose a thinking flag at all.

**What we have.**

- Vendor-side data for one model showed a **0% thinking-fire rate** under a named professional
  persona.
- An independent production soak by another operator corroborated **~0.1%** in a setting that
  carried both a persona **and** a task gate simultaneously, so the two suppressors are confounded.
- Our own runs of that model with a persona did not surface thinking; without one, they did. That is
  an observation across a handful of sessions, not a measured rate.

**Why it matters for this registry.** If two teams report wildly different thinking rates for the
same model at the same flag settings, persona may be the hidden variable, which makes it a
config-explains-the-number trap rather than a model property.

**What would settle it.** Run the same prompt set twice against the same endpoint, identical
sampling and identical thinking flag, varying only the system persona:

- arm A: no persona (bare task instruction)
- arm B: named professional-identity persona
- arm C: persona **plus** a task gate, to separate the two suppressors that the production soak
  confounded

Report thinking-fire rate per arm, plus reasoning-token count per turn. n large enough to beat the
right-skewed variance, the same variance that drives Trap 30, so at least 50 turns per arm.

Then repeat on a second model family. A single-family effect is a model quirk; a cross-family effect
is a lever worth a full entry.

**Known confound to control.** Some templates ignore `enable_thinking` entirely and require an
explicit no-think token instead. Verify at smoke-test that your OFF arm actually zeroed reasoning
before attributing any suppression to the persona.

**Attribution.** Vendor-published figure and the independent production soak are credited to their
respective sources; the cross-family generalization question is ours.

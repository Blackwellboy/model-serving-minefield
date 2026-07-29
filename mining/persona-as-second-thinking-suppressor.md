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

---

## Maintainer adjudication, 2026-07-29

**Accepted as a mining candidate. Largely ANSWERED, and in TheTom's favour.**
Everything above this line is his text as submitted in PR
[#1](https://github.com/Blackwellboy/model-serving-minefield/pull/1) and is
unedited. This section is ours.

**His experiment was run without either side realising it.** The arms he
specified (A bare, B named professional persona, C persona plus a task gate,
at least 50 turns per arm) are the arms of a grid we ran separately: ten
conditions, n=40 per cell, 400 turns, one build, one prompt set, varying only
the system prompt. His arm A is our C0. His arm B is our C4. His arm C is our
C5 through C7. Data:
[laguna-s21-lab/gate-study](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/gate-study).

**Persona is a real lever.** Firing falls from 30/40 bare to 18/40 under a
named professional persona, and to 3/40 under that persona plus a ten-rule
block.

**The effect is persona-by-task, not universal suppression.** Pooled numbers
hide it. Split by task, on code:

| Condition | System prompt | Code fired |
|---|---|---|
| C0 | none | **10/10** |
| C4 | named professional ("Alex, senior staff engineer") | **0/10** |
| C7 | full agent prompt | **10/10** |

Code is the persona-sensitive task, and C4 reproduces his 0% exactly, on the
same persona wording he named. Math is 10/10 in all three. So a persona does
not suppress thinking in general; it suppresses it on particular task shapes.
That is a stronger result than the one he claimed, and it is the mechanism by
which two teams can report wildly different rates at identical flags, which is
the property he said made it registry-worthy.

**The ~0.1% production soak is ours, and it is not a clean persona result.**
He was right to flag it as confounded, and more right than he knew. That run
carried a persona, a task gate and a 100K-plus context simultaneously, so
persona, task shape and depth all moved together. Our own grid says a system
prompt alone does not get anywhere near 0.1%. It should never have been read
as a persona-only figure, and it is not evidence for this candidate in either
direction. Counts and derivation:
[laguna-s21-lab soak](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/soak).

**Promotion gate: cross-family evidence.** This is one model family. One family
makes it a model quirk. The gate is the second family he named, and it is
unchanged by anything above.

**Not promoted to a numbered trap**, and deliberately so: the cross-family arm
is the entry bar and it has not been run.

**Credit.** The candidate, the framing and the arm design are TheTom's. The
grid that answered it is ours.

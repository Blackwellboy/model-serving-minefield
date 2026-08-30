# Trap 06: system-prompt topology moves the thinking gate; the prefix key is reported, not reproduced on a second stack

> The filename and the `06-identity-sentence-eviction` slug are kept for
> stable links. They name the **reported** mechanism, not a settled one. The
> title above is what this entry actually establishes.

**Found by @quantumleap68.**

**Status: reported by others; independently tested on a second stack, where
the prefix-key mechanism did NOT reproduce (a position-generic tail effect
was found instead).** (@quantumleap68, wire-level, N of at least 6 per cell;
independent test: two builds, interleaved controls, n=40 per cell.)

**Symptom.** Thinking collapses under any real system prompt, and no amount
of instruction tuning brings it back. Appending "always think", raising
verbosity, or rewording the prompt does nothing. It looks exactly like
generic prompt-dose suppression, so you tune the prompt harder and measure
the same zero.

**Before you read the mechanism: this symptom has more than one cause, and
the one below is the one that did NOT replicate.** If you arrived here with a
big agent system prompt and tool schemas, go to
[the apparatus and task route](#if-you-arrived-here-with-an-agent-prompt-and-tools)
at the bottom first. A 752-byte agent prompt with three tool schemas fired
**90.4% at n=492** on a coding battery, so "a real system prompt closes the
gate" is not a general fact and should not be your first hypothesis.

**Mechanism (reported, and refuted at its critical cell by the replication
below).** The template's trained identity sentence, the default "You are ..."
line the model was trained to see first, was reported to act as a **pure
prefix key** for the thinking gate: replace it with your own system prompt
and the gate closes, content barely mattering and position carrying the
effect. An independent test on a second stack did **not** reproduce that at
the cell that defines it, and found a tail effect with the opposite geometry
instead. What both results share, and all this entry establishes, is that
**system-prompt topology moves the gate**: which end of the prompt carries
the lever is stack-dependent, and the identity text itself carried no special
weight on the stack where it was tested against matched filler.

**Stacks and builds bitten.** Laguna S 2.1, measured at the wire by
@quantumleap68 (his CLI client to vLLM 0.25.1, NVFP4 TP=1 and FP8 TP=2, logging
proxy, N of at least 6 per cell). His measured cells: no system message
**8/8** fired; "You are a helpful assistant." **6/6**; a full 40K agent
prompt **0/8**; the same 40K prompt with the identity sentence prepended as
the literal first line **6 to 7 of 8**; identity appended at the **end** of
the prompt **0/8**; identity spliced mid-sentence **1/6**; identity intact as
line one plus a sentence after it **4/6**. A pure prefix prior: presence is
not enough, position is the variable.

**Independent test on a second stack.** A replication attempt on a different
stack (direct HTTP client to vLLM, Laguna S 2.1 3.25bpw hybrid and NVFP4
builds, 4 tasks x 10 samples per cell, single-turn, thinking enabled) did not
reproduce the prefix key at its critical cell: the trained identity sentence
prepended as the literal first line of a 10-rule system prompt fired **0/40**
(vs 5/40 for the same prompt as-is), and a full agent prompt was unmoved by
the prefix (17/40 both ways). What did reproduce is a **tail** effect with
the opposite geometry to the wire-level report: roughly 29 tokens of ANY
token-band-matched text appended to the END of the system prompt reopened
the gate on both builds (hybrid: bare 0/40 vs identity/neutral/topical tails
13/14/10 per 40, every suffix vs bare p <= 0.001; NVFP4: bare 2/40 vs
17/10/11 per 40, every suffix vs bare p <= 0.025), with identity text
carrying no special weight (identity vs neutral filler p = 1.0 on hybrid,
NS on NVFP4). Both suffix runs were in-run interleaved with seeded
per-quartet shuffling. An ungated control model (Qwen3.6-35B-A3B) fired
480/480 across all arms. Note the original report and this test also
disagree at the tail cell itself (0/8 reported vs 13-18/40 measured), and
the original report already found FP8 and NVFP4 behave differently, so
treat both results as stack-scoped, and control BOTH ends of the system
prompt in any prompt-dose measurement.

**The check.** Prepend the template's own default identity sentence as the
literal first line of your system message and re-measure firing. If the rate
recovers, you were looking at identity eviction, not instruction-dose
suppression, and every "prompt dose" number you took without controlling the
first line is confounded. Position of the check matters by stack: on the
tested second stack the recovery lever was the tail, not the first line. Run
the check both ways (identity as line one, and any ~30-token matched text
appended at the end) before concluding which mechanism you have.

**The fix.** Stack-dependent. Where the prefix key holds (the originating
stack), keep the trained identity sentence as the literal first line. On the
tested second stack the working lever was appending ~30 tokens of any text
at the tail. Either way, control the first line AND the tail in any
prompt-dose measurement; do not assume the mechanism transfers across
serving stacks, quant builds, or client paths.

## If you arrived here with an agent prompt and tools

The symptom row that routes here says "thinking dies under any real system
prompt". That phrasing dates from when the prefix key was the only candidate
mechanism, and it is too strong. Upstream now treats the gate as
**conditioned on the apparatus and the task**, not only on prompt topology,
and that model is the one to try first if you are running an agent:

- **The apparatus does not necessarily close the gate.** @apollo-mg published
  an apparatus cell at **n=492** (HumanEval+ 164 x K=3, Laguna S 2.1
  UD-Q2_K_XL under llama.cpp on 4x Tesla P100 sm_60, a 752-byte agent system
  prompt plus 3 tool schemas): thinking fired on **445/492 samples (90.4%)**
  with mean `reasoning_content` of 4,686 chars
  ([offlabel PR #10 comment 5093534067](https://github.com/TheTom/offlabel/pull/10#issuecomment-5093534067),
  2026-07-27, raw published). A full agent prompt and three tool schemas, and
  the gate stayed open at scale. Any claim that a real system prompt closes
  the gate has to survive that cell, and it is far larger than anything in
  this entry.
- **What looks like suppression on tool turns is often truncation.** A turn
  that exits via `tool_calls` has a structurally shorter reasoning episode
  because it stops to call the tool. The depth reading did not survive in-run
  interleaved control (all pairwise p >= 0.13). See
  the caveat in the r2-39 mining note *(private evidence archived)*
  for both narrowings.
- **If your scores dropped rather than your firing rate**, you are in
  [trap 42](../evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md),
  not here: a single-turn harness scores `finish_reason=tool_calls` as a
  wrong answer, which costs measured score without costing capability.

**Why there is not yet a registry entry of its own for the apparatus gate.**
The n=492 cell is a contributor measurement on one stack, one model build and
one battery, and it is a **negative** (the gate did not close). Our own
counter-evidence is n=40 cells, which that cell bounds rather than
contradicts. Nobody has yet run the discriminating experiment: apparatus dose
against task type, with topology held fixed, on more than one stack. Until
someone does, this section is the route, and it is deliberately a pointer to
a contributor's published raw rather than an entry asserting a mechanism we
have not established.

**Found.** 2026-07-27, reported from wire-level measurement.

**Attribution.** @quantumleap68. Independent test on a second stack
completed 2026-07-27: the prefix-key mechanism did not reproduce there; a
position-generic tail effect was found instead (two builds, interleaved
controls). Full data, drivers, and raw per-turn JSONLs:
[laguna-s21-lab `identity-prefix/`](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/identity-prefix).

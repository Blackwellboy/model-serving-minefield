# Trap 06: identity-sentence eviction, the thinking gate keys on the literal first line

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

**Mechanism.** The template's trained identity sentence, the default
"You are ..." line the model was trained to see first, acts as a **pure
prefix key** for the thinking gate. Replace it with your own system prompt
and the gate closes. The content of your prompt barely matters; its
*position* does.

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

**Found.** 2026-07-27, reported from wire-level measurement.

**Attribution.** @quantumleap68. Independent test on a second stack
completed 2026-07-27: the prefix-key mechanism did not reproduce there; a
position-generic tail effect was found instead (two builds, interleaved
controls). Full data, drivers, and raw per-turn JSONLs:
[laguna-s21-lab `identity-prefix/`](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/identity-prefix).

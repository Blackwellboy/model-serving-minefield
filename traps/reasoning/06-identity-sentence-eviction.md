# Trap 06: identity-sentence eviction, the thinking gate keys on the literal first line

**Found by @quantumleap68.**

**Status: reported by others** (@quantumleap68, wire-level, N of at least 6 per cell); under independent test on our stack.

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

**The check.** Prepend the template's own default identity sentence as the
literal first line of your system message and re-measure firing. If the rate
recovers, you were looking at identity eviction, not instruction-dose
suppression, and every "prompt dose" number you took without controlling the
first line is confounded.

**The fix.** Keep the trained identity sentence as the literal first line of
the system prompt when you need thinking to fire, and control for it in any
prompt-dose measurement.

**Found.** 2026-07-27, reported from wire-level measurement.

**Attribution.** @quantumleap68. Independently under test on a second stack
at the time of writing; that result is not yet in, and this entry will be
updated when it lands.

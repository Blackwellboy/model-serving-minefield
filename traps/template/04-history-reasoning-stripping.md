# Trap 04: prior-turn reasoning stripped from history, and the model reads it

**Status: reproduced here** (quantified stripped-vs-preserved comparison) and independently confirmed at the wire by @quantumleap68 on a second client and serving pair.

**This is the most dangerous entry in this registry.** Its symptom is not a
broken parse or a corrupted string. Its symptom is a *plausible, publishable,
wrong finding about model behavior*.

**Symptom.** Thinking fires normally at single turn and collapses toward
zero as the conversation deepens. It looks exactly like a genuine,
interesting property of the model. Measured on Laguna S 2.1: **60 to 72%
firing single-turn** against **~0.1% across a 12-hour multi-turn soak**
(3 of 3,096 turns), with real effort spent theorizing about "context mass"
and "turn depth" as the mechanism. The mechanism was the template.

**Mechanism.** With thinking enabled, the chat template renders prior
assistant turns into the history **without** their reasoning, emitting an
empty `<think></think>` block where the reasoning used to be, unless the
reasoning is explicitly resent and preserved. The model then reads its own
history as evidence that it does not think in this conversation, and
suppresses accordingly. The control is a **`preserve_thinking`** kwarg that
the template reads and **the model card does not document**.

Confirmed and quantified on identical transcripts probed with prior-turn
reasoning stripped versus resent: **0/10 vs 10/10 firing at depth 10 / ~8K
tokens, and 0/10 vs 10/10 at depth 20 / ~8K** (3.25bpw hybrid lane, 45%
single-turn baseline). The surrounding 15-cell depth-by-mass sweep, all
client-default stripped histories, fired 0/150 with flat-zero curves on both
axes: depth and mass are epiphenomenal to the stripping.

Independently confirmed on a second stack and client by @quantumleap68 at the
wire level (Hermes CLI to vLLM 0.25.1, Laguna NVFP4 TP=1 and FP8 TP=2, a
logging proxy between client and server, N of at least 6 per cell): a client
that strips reasoning from replayed history renders each prior turn as an
empty `<think></think>`, and the collapse tracks turn-by-turn. Turn 1: 199
reasoning deltas; turns 2 and 3 with stripped history: none.

**Stacks and builds bitten.** A 12h production soak on Laguna S 2.1 NVFP4 /
vLLM, plus the 3.25bpw EXL3-hybrid lane, plus @quantumleap68's independent
client and serving pair. Four independent testers characterized this model
and **all four missed it**, because every check anyone ran was
request-shaped: correct kwargs, correct response parsing, correct field
names. Nobody dumped the assembled prompt at turn N.

**The check.** Assemble a three-turn conversation whose first assistant
message carries a uniquely marked reasoning string, render the actual prompt
through your serving path, and grep it for that marker. If it is absent, your
multi-turn numbers describe a model that cannot see its own thinking. Then
diff the render with and without the preservation kwarg.
[`checks/preflight_template.py`](../../checks/preflight_template.py) in this
registry does exactly this and refuses to pass the lane if the marker is
missing.

Corollary worth internalizing: **enumerate every kwarg the template reads and
diff it against the model card.** Anything read-but-undocumented is an
untested variable, and if it sits near a thinking branch, assume it changes
your results until you have shown it does not.

**The fix.** Resend `reasoning` on prior assistant messages (with thinking
on, the template then renders the real think blocks; verified passthrough
moves prompt_tokens accordingly), or set `preserve_thinking: true` for
thinking-off flows. Cost is roughly 250 to 320 prompt tokens per preserved
turn that carries reasoning (measured: +1,615 prompt tokens over 5 preserved
turns at depth 10, +4,764 over 19 at depth 20). Partial preservation
suffices at moderate depth: a depth-10 history carrying reasoning on only
5 of 10 turns still recovered 10/10 firing.

For tooling authors, @quantumleap68's client-side pattern is the right shape:
opt providers into echoing reasoning on replay via an explicit per-provider
capability flag, rather than vendor-sniffing which models need it.

One measurement note for replicators: a session cannot bootstrap its own
preserved history. Once the gate closes at turn 2, live-accumulated turns
contain no reasoning to preserve (a first arm was vacuous exactly this way,
0/50 turns, kept in the raw logs). Generate history turns statelessly.

**Found.** 2026-07-26, after a gate study published; mechanism confirmed and
quantified 2026-07-27; wire-level independent confirmation 2026-07-27.
(Dates re-anchored to shipping commits 2026-07-27; earlier copies of this
registry carried campaign-day labels written ahead of the clock.)

**Attribution.** Community-surfaced: the lead was @quantumleap68's, who also
provided the independent wire-level confirmation. Quantification by
Blackwellboy. Raw data and writeup:
[context-mass/](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/context-mass).

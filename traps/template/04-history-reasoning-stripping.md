# Trap 04: prior-turn reasoning stripped from history, and the model reads it

**Found by @quantumleap68 and Blackwellboy.**

**Status: reproduced here** (quantified stripped-vs-preserved comparison) and independently confirmed at the wire by @quantumleap68 on a second client and serving pair.

**This is the most dangerous entry in this registry.** Its symptom is not a
broken parse or a corrupted string. Its symptom is a *plausible, publishable,
wrong finding about model behavior*.

**Symptom.** Thinking fires normally at single turn and collapses toward
zero as the conversation deepens. It looks exactly like a genuine,
interesting property of the model, and real effort went into theorizing
about "context mass" and "turn depth" as the mechanism. The mechanism was
the template.

**The controlled result, which is the one to quote.** Identical transcripts,
prior-turn reasoning stripped versus resent, nothing else varied:
**0/10 versus 10/10 firing at depth 10, and 0/10 versus 10/10 at depth 20**
(3.25bpw hybrid lane, ~8K tokens, 45% single-turn baseline). One variable,
total separation, plus a wire-level confirmation on a second client and
serving pair. That is the entry.

**A 12-hour production soak is consistent with it, and is not a measurement
of it.** The soak fired on 3 of 3,096 turns (~0.1%) against a 60 to 72%
single-turn rate elsewhere. Those two numbers are not a controlled contrast
and an earlier version of this entry led with them as though they were: the
soak carried agent apparatus, tool schemas, a replaced system prompt and
different client field names, any of which moves firing on its own
([trap 42](../evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md),
[trap 30](30-default-system-message-silently-replaced.md),
[trap 20](../reasoning/20-reasoning-write-field-name-diverges.md),
[trap 06](../reasoning/06-identity-sentence-eviction.md)). Read the soak as a
multi-confounded production rate that is consistent with the mechanism, and
quote the 0/10 versus 10/10 for the magnitude.

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
wire level (his CLI client to vLLM 0.25.1, Laguna NVFP4 TP=1 and FP8 TP=2, a
logging proxy between client and server, N of at least 6 per cell): a client
that strips reasoning from replayed history renders each prior turn as an
empty `<think></think>`, and the collapse tracks turn-by-turn. Turn 1: 199
reasoning deltas; turns 2 and 3 with stripped history: none.

**Cross-family confirmation of the template mechanism, with a divergent
consequence (2026-07-27, standardized probe sweep).** The Qwen 3.6 chat
template carries the same machinery: prior-turn reasoning is dropped from
assembly by default, and a `preserve_thinking` kwarg gates a branch that
renders it back (`(preserve_thinking is defined and preserve_thinking is
true) or (loop.index0 > ns.last_query_index)` in the template read live
from the serving lane). Measured on Qwen3.6-27B Q4_K_M / llama.cpp b9193:
a three-turn replay with reasoning resent assembled to the same 60 prompt
tokens as the stripped arm by default, and to 115 with
`preserve_thinking: true`. Two divergences from the Laguna case:

- **Rendering differs.** Qwen 3.6's default branch renders the prior turn
  with no think block at all, where Laguna renders an empty
  `<think></think>`. Only Laguna's rendering plants an explicit
  "I did not think here" signal in the history.
- **The behavioral collapse does not follow.** Qwen fired on the probe turn
  in both arms (stripped and preserved) in every sample taken. The
  template-side stripping is cross-family; the firing collapse it causes on
  Laguna is, so far, Laguna's.

**And the fix is version-dependent within a family.** The Qwen3.5-9B
template (same serving stack) reads no `preserve_thinking` at all; resending
reasoning changed assembly by zero tokens with and without the kwarg. If
your pipeline standardizes on "resend reasoning plus preserve_thinking",
that fix silently no-ops on the family member whose template never reads
it. Enumerate the kwarg surface per model version (the check below), not
per family.

**MLX confirmation of the stripping shape (2026-07-27, stock mlx_lm,
prism-ml Ternary-Bonsai-27B-mlx-2bit, Apple silicon).** The shipped
template's history path reads `reasoning_content` with a
`preserve_thinking` gate (`(preserve_thinking is defined and
preserve_thinking is true) or (loop.index0 > ns.last_query_index)`), while
the server emits `reasoning`
([trap 20](../reasoning/20-reasoning-write-field-name-diverges.md) has the
divergence and the marker probe that confirmed it behaviorally). Two
consequences: by default, reasoning on turns at or before the last user
query is stripped, so multi-turn thinking studies on such a lane measure a
model that cannot see its own prior reasoning unless the client both
renames the field and sets the kwarg. And the preserved branch renders a
think-open, the reasoning, and a think-close even when `reasoning_content`
is the empty string, which is
[trap 25](25-empty-think-blocks-poison-prefix-cache.md)'s empty-shell
render pattern (structural read only; cache timing not tested there).

**Stacks and builds bitten.** A 12h production soak on Laguna S 2.1 NVFP4 /
vLLM, plus the 3.25bpw EXL3-hybrid lane, plus @quantumleap68's independent
client and serving pair. The rendering half is also reproduced by @Defilan
on llama.cpp (Laguna S 2.1 Q4_K_M, Vulkan on gfx1151, deterministic via
`/apply-template`): three prior content-only turns render as three empty
think blocks, byte for byte; behavioral suppression on that stack is under
test. Four independent testers characterized this model
and **all four missed it**, because every check anyone ran was
request-shaped: correct kwargs, correct response parsing, correct field
names. Nobody dumped the assembled prompt at turn N. Template mechanism
confirmed cross-family on Qwen 3.6 (llama.cpp b9193); preservation kwarg
absent on Qwen 3.5 (llama.cpp b9066).

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

**The fix.** Resend prior-turn reasoning on assistant messages, **under the
field name your runtime actually reads**: `reasoning` on vLLM (0.25.1, this
model's parser; verified passthrough moves prompt_tokens 63 to 303),
`reasoning_content` on llama.cpp, where `reasoning` is silently dropped and
renders byte-identical to the stripped arm. The remedy does not port by
copying the field name; both wrong-field cases fail silently by producing
absence, so probe your lane first
([trap 20](../reasoning/20-reasoning-write-field-name-diverges.md) has the
probe). Alternatively set `preserve_thinking: true` for
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
Blackwellboy. llama.cpp rendering replication and the write-field divergence
by @Defilan
([offlabel #16](https://github.com/TheTom/offlabel/issues/16#issuecomment-5086926968)).
Raw data and writeup:
[context-mass/](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/context-mass).

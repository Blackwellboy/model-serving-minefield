# U41: speculative drafts created before reasoning ends can be invalid under the grammar that activates mid-window

**Reported by @chaunceyjiang.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** vLLM merged PR #53046 with a targeted regression test for the speculative reasoning-end / structured-output transition.

**Issue state: closed, fixed.** vLLM PR #53046 is merged as `c6e19b3be24338759a443e03c8325d76da9ee202`.

**Primary source.** Merged [vLLM PR #53046](https://github.com/vllm-project/vllm/pull/53046), read on 2026-08-30.

**Symptom.** A multi-token speculative window can straddle the end of a model's reasoning section. Draft tokens produced before that boundary were generated while the structured-output grammar was not yet active, but after the reasoning-end marker the serving path can try to advance the newly active grammar with one of those pre-boundary draft tokens. The reported result was repeated `Failed to advance FSM` errors even though the failure was an artifact of state timing rather than proof that the target response violated the grammar.

**Mechanism.** The grammar state changes inside one speculative verification window. When `post_reasoning_end_in_window` is true, the affected path used to send the token directly to `grammar.accept_tokens()`. The merged fix first asks `grammar.validate_tokens([token])`; only a token valid under the now-active grammar is committed. A draft token generated before grammar activation can therefore be rejected as stale-to-the-new-state without spuriously advancing/failing the FSM.

This is distinct from U40. U40 stops a grammar token batch once the matcher itself terminates on stop/EOS. U41 handles the opposite transition: the grammar becomes relevant **during** a speculative window after reasoning ends, while some draft tokens in that window were generated under the earlier no-grammar state.

**What we have not done.** We have not reproduced this reasoning-end/speculative structured-output transition on Blackwellboy infrastructure.

## If you have this stack

Pin a pre-fix vLLM build with a reasoning parser, XGrammar structured output and speculative decoding. Construct a request where the reasoning-end marker lands inside a multi-token speculative window and at least one later drafted token was proposed before grammar activation. Capture the scheduled speculative IDs, reasoning-boundary position and FSM errors. Repeat on PR #53046's merged commit or a descendant.

**CONFIRM.** The pre-fix build directly advances the newly active grammar with a pre-boundary draft token and produces the spurious FSM failure, while the fixed build validates that token first and no longer logs the failure under the matched request.

**REFUTE.** The pre-fix path already validates pre-boundary drafts before grammar advance, or the same FSM failure persists after the merged validation-before-advance logic is proven active.

## Attribution

Reported and fixed upstream by @chaunceyjiang in vLLM PR #53046. The registry has not independently reproduced the measurement.

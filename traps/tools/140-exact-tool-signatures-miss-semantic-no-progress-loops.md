# Trap 140: exact tool-call hashes miss semantic no-progress loops

**Found by Blackwellboy.**

**Status: measured here, raw not published.** First-party live-agent traces are retained in the private evidence archive under the 2026-09-13/14 Qwen3.8 terminal-loop findings. This entry publishes the bounded event counts, mechanism, check, and mitigation without private task/session content.

**Symptom.** An agent repeatedly prepares or calls tools, but an exact-duplicate guard never fires because every call is technically different. The arguments vary slightly while pursuing the same failed operation. The run can spend many calls making no useful progress and stop only when another guardrail fires.

A measured instance had 12 terminal-related events with 12 unique exact command hashes but only about four semantic operation classes. After three early executions, nine consecutive large inline-script attempts were rejected as structurally incomplete. Every rejected call had different arguments, so an exact `tool_name + hash(canonical_args)` denylist correctly treated them as distinct even though the agent was repeating the same failed script-generation strategy.

**Mechanism.** Exact-signature loop guards answer the narrow question "did the model emit the same call again?" They do not answer "did the model retry the same failed strategy with cosmetically different arguments?" A model can therefore evade an exact-call guard unintentionally: regenerate a large script, change a few tokens, receive the same structural rejection, and repeat. Tool results can be delivered correctly every time; the failure is strategy-level adaptation, not parser or feedback loss.

In the measured lane the existing safeguards were individually correct: malformed inline scripts were rejected before execution, and the identical-call guard correctly did not collapse different hashes. The missing layer was a bounded rejection-class or semantic-strategy guard.

**Stacks and builds bitten.** Measured on Hermes Agent using Qwen3.8-27B-OBLITERATED Q4_K_M through llama.cpp/TurboQuant on RTX 5090 and reproduced as the same strategy family on an RTX 3090 lane with byte-identical GGUF weights. The exact manifestation depended on the Hermes guardrail revision, but the generic trap is agent-runtime-wide: any loop detector keyed only by exact tool arguments can miss near-duplicate no-progress behavior.

**The check.** Record both an exact signature and a coarse semantic/rejection class for each tool attempt, plus whether the task state materially advanced. A minimal reproduction is three distinct calls whose exact hashes differ but whose semantic class and rejection class are the same, with no progress between them.

For example:

```text
script-generation variant A -> INCOMPLETE_SCRIPT
script-generation variant B -> INCOMPLETE_SCRIPT
script-generation variant C -> INCOMPLETE_SCRIPT
```

If the third call is allowed only because its bytes differ, exact-signature protection is insufficient for that failure class.

Do not infer semantic equivalence from tool name alone. Different terminal commands can be legitimate sequential progress. The check needs either a structural rejection class, a normalized operation family, or an explicit progress signal.

**The fix.** Keep the exact-call guard, then add a bounded second layer keyed to repeated failure class or semantic strategy. In the measured fix, repeated incomplete inline-script rejections degraded and then disabled that script-in-terminal strategy for the remainder of the turn while leaving short terminal commands available and steering large source generation toward a file-writing tool. Do not simply raise retry limits; a larger allowance only buys more variants of the same failed plan.

**Found.** 2026-09-13, while live-observing repeated Hermes terminal-preparation events after an exact-signature guard had already been added.

**Attribution.** Blackwellboy.

**Related.** [139](139-system-prompt-drift-invents-cli-detours.md) covers a different upstream cause where system-prompt guidance changes the agent's first tool choice before a loop begins. [136](../evaluation/136-pipeline-reports-consumer-status-not-producer-failure.md) is another case where the visible wrapper-level status hides the state of the producer underneath.

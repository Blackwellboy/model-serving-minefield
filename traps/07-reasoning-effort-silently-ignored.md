# Trap 07: `reasoning_effort` accepted and silently ignored

**Symptom.** Effort levels change nothing. Identical reasoning depth at
`low`, `medium`, and `high`, and you conclude the model ignores depth
requests, or worse, publish a "reasoning_effort has no effect on this model"
finding as if the knob had been exercised.

**Mechanism.** The request schema accepts a `reasoning_effort` parameter,
the server returns 200, and the chat template has **no handling for it at
all**. The parameter parses, validates, and does nothing. On templates like
this, prompting is the only depth lever that exists.

**Stacks and builds bitten.** Laguna S 2.1 on vLLM 0.25.1, measured at the
wire by @quantumleap68 (Hermes CLI, logging proxy): `reasoning_effort` is a
no-op because the template never reads it. Same class as Trap 04's corollary
in reverse: there, the template read a kwarg the model card did not document;
here, the API accepts a parameter the template does not read. Both directions
of the schema/template mismatch produce silent wrong numbers.

**The check.** Grep the chat template for the parameter name **before**
trusting any knob you send. If the template never references it, the knob is
dead on this build regardless of what the server accepts. The general rule:
diff the set of kwargs the template reads against the set the API accepts,
in both directions.
[`checks/preflight_template.py`](../checks/preflight_template.py) enumerates
the template's kwarg surface for you.

**The fix.** Remove the dead knob from your configs and your conclusions.
If you need depth control on such a template, it has to come from the prompt.

**Found.** 2026-07-30, reported from wire-level measurement.

**Attribution.** @quantumleap68.

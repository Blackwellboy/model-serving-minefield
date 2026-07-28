# Trap 43: chat template gates tool args on `is mapping`, emits an empty call for string args

**Found by TheTom.**

**Status: reproduced here.** Render-tested before and after on the template in question; raw logs
held outside the tree and can be produced on request, per the default in
[MAINTAINING](../../MAINTAINING.md#shipping-raw-data-in-the-repo).

**Symptom.** An agent emits `<function=NAME></function>`: a tool call with no parameter body, and
then loops, retrying the same call. Only happens on turns that *replay* a previous tool call; the
first call in a fresh conversation is fine. Reads as "this model is bad at tool calling."

**Mechanism.** The chat template expands tool-call parameters inside a branch gated on
`tool_call.arguments is mapping`, with **no `else`**. But the OpenAI spec says `arguments` **is a
string**, so any framework that replays a prior call with pre-serialized JSON hits the guard, the
whole parameter block is skipped, and an empty call is rendered. The model then sees its own
malformed call in history and retries.

This is a *dialect* bug, not a model bug: the same weights emit correct calls when the template
handles both shapes.

**Stacks and builds bitten.** Any Jinja chat template with this shape. Confirmed in an XML-dialect
tool template (`<tool_call><function=NAME><parameter=KEY>...`); the equivalent ChatML/JSON dialect
templates have their own variants of the same guard. Engine-independent, it's the template, so it
bites llama.cpp/minja, vLLM, and anything else rendering the same file.

**The check.** Render the template twice with the same logical call, once with `arguments` as an
object and once as a JSON **string**, and assert both produce a non-empty parameter body. Runnable:
[`checks/tool_args_dialect_probe.py`](../../checks/tool_args_dialect_probe.py), it also has a live
mode that sends a real `tools` array to an endpoint and asserts structured `tool_calls` come back
rather than prose or an empty call.

```
$ python3 checks/tool_args_dialect_probe.py --template ./chat_template.jinja
  object args : PASS (parameter body present)
  string args : FAIL (empty <function=NAME></function>)
```

**The fix.** Add an `elif` after the mapping branch, leaving the mapping branch **byte-identical**
so existing behavior can't regress:

```jinja
{%- if tool_call.arguments is mapping %}
    ...existing per-key parameter loop, UNCHANGED...
{%- elif tool_call.arguments is string and tool_call.arguments|trim %}
    {{- '<parameter=arguments>\n' + tool_call.arguments + '\n</parameter>\n' }}
{%- endif %}
```

Avoid a `fromjson`-based fix that parses the string and re-expands per key: `fromjson` support is
inconsistent across the Jinja implementations embedded in inference engines, and a render-time
failure is a serving outage rather than a degraded call.

**Verification after patching:** confirm the template KV is the *only* thing that changed. In our
case a "compat" republish of the same model was verified as zero-weight, identical per-tensor
SHA-256 across all 866 tensors including the MTP head, with only `tokenizer.chat_template`
differing. If tensors changed too, you are not applying a template fix, you are swapping models.

**Related trap.** Do **not** adopt someone else's template wholesale to get this fix. Two templates
can both be "correct" and be different **wire formats** (XML parameter tags vs ChatML JSON args).
Weights fine-tuned to emit one dialect, served under the other, break tool calling on *normal*
turns, worse than the bug being fixed. Port the fix, not the file.

**Found.** 2026-06-22, while deciding whether a third-party "compat" republish of a fine-tune
warranted a retrain. It did not; it was template-only.

**Attribution.** TheTom. The upstream template-fix idea is credited to the third-party publisher
whose release prompted the investigation; the string-args `elif` and the no-`fromjson` constraint
are ours.

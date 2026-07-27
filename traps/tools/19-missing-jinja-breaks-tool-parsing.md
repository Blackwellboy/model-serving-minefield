# Trap 19: one missing server flag turns structured tool calls into prose

**Status: reported by others** (TheTom, measured on two llama.cpp forks); consistent with our native-path data from the serving side.

**Symptom.** The model "cannot do tool calling": it describes the call in
prose instead of returning a structured `tool_calls` array. Every harness
downstream breaks, and the model takes the blame in a bug report.

**Mechanism.** On llama.cpp, `--jinja` is load-bearing: without it the
model's own chat template and its differential tool-call autoparser never
run, so tool calls stop parsing regardless of what the client sends. The
same guide measured the template side of this cliff: native template 83%
tool-call success versus **0% through a generic chatml path**
([TheTom's guide](https://github.com/TheTom/offlabel/blob/main/models/laguna-s-2.1.md),
setup-verification table and section 4). The flag and the template are two
doors to the same cliff: the request can be perfect and the serving path
still guarantees prose.

Our corroborating data from the vLLM side of the same model: the native
parser path ran a 12-hour production soak with every scored tool task
succeeding, while a third-party generic-OpenAI-path benchmark aggregate on
the same model landed at 0.21
([operators guide, tool calling](https://github.com/Blackwellboy/laguna-s21-lab/blob/main/LAGUNA_OPERATORS_GUIDE.md)).
Wherever the native path is dropped, structured calling degrades to
somewhere between poor and zero.

**Stacks and builds bitten.** llama.cpp forks serving Laguna S 2.1
(measured by TheTom); the flag specifics are llama.cpp's, the class
(server-side template/parser flags silently deciding tool-call success) is
runtime-general.

**The check.** One request with one tool defined, before anything else:
assert the response contains a structured `tool_calls` array, not prose
describing a call. If prose: check the serve line for the template/parser
flags before touching the client.

**The fix.** Serve with the model's native template and tool parser
enabled (`--jinja` on llama.cpp; the model-specific
`--tool-call-parser` on vLLM), and never fall back to a generic chat
template for a tool-calling model.

**Found.** Published in the guide, 2026-07.

**Attribution.** TheTom (flag and template measurements); Blackwellboy
(vLLM-side corroboration).

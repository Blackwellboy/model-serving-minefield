# Trap 29: the server's reasoning-off flag is not an off switch

**Found by Blackwellboy.**

**Status: reproduced here** (two production llama.cpp lanes, n=3 and n=2,
plus negative controls), and reproduced on a second stack (mlx_lm,
2026-07-27). **Evidence:** the check below is a two-request procedure you can
run on your own lane, which is what makes this checkable without us. Our own
rows are **not** published, so treat the n=3 and n=2 counts as our conditions
rather than as figures you can verify, and do not quote them as a measured
rate; the finding is the direction, and you can re-derive that yourself in
two requests.

**Symptom.** Blank assistant turns (content empty, finish_reason=length,
large reasoning field) only on requests from one particular client, while
identical prompts from other clients complete fine at the same
max_tokens. The lane was serving with reasoning disabled, so nobody was
budgeting for thinking tokens.

**Mechanism.** You serve a thinking-family model with reasoning disabled
in the server config (our lanes carry `--reasoning off` in ExecStart,
llama.cpp b9193). You size every client max_tokens for non-thinking
outputs, e.g. 8192, and everything works. Then any client passes
`chat_template_kwargs: {"enable_thinking": true}` and that single request
thinks anyway: measured 15K to 61K chars of reasoning on a hard coding
task, blowing through the 8192 cap and returning finish=length with
empty content ([trap 12](../evaluation/12-empty-content-at-token-ceiling.md)'s
signature). The server flag looked like a guarantee. It is a default,
not a gate.

**Stacks and builds bitten.** llama.cpp b9193 serving Qwen3.6-27B Q4_K_M
and the same family at 35B Q3, both with `--reasoning off` in the serve
line; raw rows in `ceiling_audit_20260727.jsonl` and
`ceiling_audit_prodarm_20260727.jsonl`.

**Second stack: mlx_lm (confirmed 2026-07-27).** A stock mlx_lm lane
serving prism-ml Ternary-Bonsai-27B-mlx-2bit on Apple silicon, launched
with `--chat-template-args {"enable_thinking":false}` (mlx_lm's spelling of
server-side thinking-off; see
[trap 03](03-enable-thinking-default-drift.md) for the toggle map). A
client sending `chat_template_kwargs: {"enable_thinking": true}` overrides
the server-side off PER REQUEST: the flag is a default, not a gate, same as
the llama.cpp case. On a lane sized for non-thinking traffic the cost is
concrete: a short arithmetic question spent 225 completion tokens with
thinking on versus 3 tokens for a comparable thinking-off reply. Combined
with mlx_lm's `--max-tokens` also being a per-request default
([trap 32](../runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md)),
this stack has NO server-side ceiling a client cannot exceed by asking.

**The check.** Send the same hard prompt twice at your production
max_tokens: once bare, once with the thinking kwarg enabled. If the
kwarg arm hits the ceiling with empty content while the bare arm
completes, every caller's kwarg surface is part of your budget model.
Grep your callers for `chat_template_kwargs`.

**The fix.** Treat max_tokens sizing as conditional on the kwarg
surface: either strip or deny thinking kwargs at the gateway for lanes
sized for non-thinking output, or size those callers for the thinking
distribution (which on our 27B has no safe ceiling at n=3 even at 16384;
see [trap 22](../evaluation/22-family-card-budget-floors-differ-by-size.md)).

**Found.** 2026-07-27, ceiling audit on the production lane trio.

**Attribution.** Blackwellboy. Related:
[trap 03](03-enable-thinking-default-drift.md) (which arm "absent" lands
in is revision- and server-dependent),
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md),
[trap 22](../evaluation/22-family-card-budget-floors-differ-by-size.md).

## Added 2026-08-30: GLM-5.3/vLLM controller setting hid reasoning but did not stop generation

**First-party Blackwellboy measurement, raw retained privately.** A GLM-5.3
NVFP4/vLLM lane was being called through an agent/controller whose own
configuration said reasoning was disabled, while the server also exposed a
reasoning parser. The request itself did **not** send
`chat_template_kwargs.enable_thinking:false`.

The live template defaulted thinking ON anyway. On the same short probe:

| request arm | completion tokens | reasoning length | visible answer |
|---|---:|---:|---|
| no template kwarg | 34 | 107 | correct |
| `enable_thinking:false` | 7 | 0 | correct |
| `enable_thinking:true` | 34 | 107 | correct |

Putting `chat_template_kwargs.enable_thinking:false` on the wire removed the
hidden reasoning without restarting the model server. The parser was a red
herring for the off-switch question: it changes how reasoning is separated or
reported, not whether the template asks the model to reason.

This adds a third practical control-plane spelling to the same trap:

- server-side `--reasoning off` can be overridden by request kwargs;
- server-side `--chat-template-args {"enable_thinking":false}` can be overridden by request kwargs;
- client/UI `reasoning.enabled:false` can merely hide reasoning while the
  template still defaults it ON if the actual chat-template kwarg is absent.

The check is therefore broader than grepping server flags: inspect the exact
request body that reaches the OpenAI-compatible endpoint and prove the
chat-template kwarg on the wire.

Full scrubbed disposition is in
[`mining/2026-08-30-glm53-thinking-level-matrix.md`](../../mining/2026-08-30-glm53-thinking-level-matrix.md).

*Status of this addendum: measured here, raw not published.*

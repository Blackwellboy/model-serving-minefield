# Trap 77: one request field is validated and every other one you invent is accepted

**Found by Blackwellboy.**

**Status: reproduced here**, 2026-07-28, on Ollama 0.32.5 with `qwen3:8b` at
temperature 0. A stranger can re-derive all of it in about two minutes against
their own install, with the two requests in the check section; both the stack
and the model are free to obtain, which is why this one is checkable rather
than merely reported.

**Symptom.** You port a working evaluation harness from one server to another.
Every request returns HTTP 200. No warnings. The thinking-off arm and the
thinking-on arm come back with **byte-identical output at temperature 0**, and
you conclude the toggle does not affect this model.

The toggle was never applied. The field your harness sends to control it does
not exist on this server, and the server accepted it anyway.

**Mechanism.** Request-body validation is not uniform. On this server exactly
one field is validated: `think` rejects a bad value with a helpful HTTP 400.
Everything else is ignored silently. Measured, at temperature 0, against a
control that sent no extra fields at all:

| Sent | Result |
|---|---|
| `think: "banana"` | HTTP 400 with a useful message |
| `enable_thinking: false` | HTTP 200, output **byte-identical to sending nothing** |
| `chat_template_kwargs: {...}` | HTTP 200, output byte-identical to sending nothing |
| an invented key nobody implements | HTTP 200, output byte-identical to sending nothing |

Placement makes no difference: top level and inside `options` behave the same.

The reason this bites harder than an ordinary unsupported-parameter case is the
**direction of the default**. The lane thinks by default. So a harness that
sends `enable_thinking: false`, gets a 200, and records the arm as thinking-off
has measured its entire thinking-off condition **on a thinking lane**, and every
number in that arm is a number about the wrong configuration.

**Stacks and builds bitten.** Ollama 0.32.5, `/api/chat` and `/api/generate`,
`qwen3:8b`, GB10 aarch64 CUDA 13. The class is general: this registry's
methodology preamble already says accepted-but-unread is a dead knob, and this
is the strongest instance of it measured here, because the server validates
enough to look like it validates.

**The check.** Two requests, and the assertion is on the response rather than
the status code:

```bash
# 1. does the server even know this field?
curl -s localhost:11434/api/chat -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"hi"}],"enable_thinking":false,"stream":false,"options":{"temperature":0}}'
# 2. the same request with the field removed
curl -s localhost:11434/api/chat -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"hi"}],"stream":false,"options":{"temperature":0}}'
```

If the two responses are identical at temperature 0, the field did nothing. Then
assert on the thing you actually care about: **an arm you believe is
thinking-off must have an absent or empty reasoning field, per request, not per
configuration.** A 200 is not evidence that a parameter was read, on any server.

**The fix.** The real control here is `think: true|false|"high"|"medium"|
"low"|"max"` on the native API, and `reasoning_effort: "none"` on the
OpenAI-compatible `/v1` route. More usefully than either: before you trust any
new server with an arm of an experiment, send one deliberately misspelled
parameter and see whether you get a 400. If you get a 200, the request surface
is unvalidated, your own typos are silent too, and every parameter you send is
a hypothesis rather than a setting.

**Found.** 2026-07-28, during first-party Ollama coverage. This is the finding
with the highest operator impact of the seven from that pass, because it
invalidates an arm rather than degrading it.

**Attribution.** Blackwellboy. Related:
[trap 07](07-reasoning-effort-silently-ignored.md), the accepted-but-not-read
class this belongs to;
[trap 03](03-enable-thinking-default-drift.md), which is why the default matters
so much here; [trap 29](29-server-reasoning-off-is-not-an-off-switch.md), the
same failure from the other direction.

## Added 2026-07-28: SGLang accepts the invented top-level field too

**SGLang 0.5.16, DGX Spark GB10, Nemotron 3 Nano NVFP4 and Laguna S 2.1
NVFP4.** The paired baseline completed with HTTP 200, and the same request with
an invented top-level field also completed with HTTP 200. The finding held on
both checkpoints. Acceptance was not treated as proof that any real field was
read: the thinking-off state was checked from the response on every measured
arm.

*Status of this addendum: contributor-measured, conditions as reported, by
[@newageinvestments25-byte](https://github.com/newageinvestments25-byte). Exact
conditions and the paired doctor assertions are in the
[SGLang DGX Spark field note](../../mining/2026-07-28-sglang-nvfp4-and-doctor-dgx-spark.md).*


## Dated addendum (2026-08-06) - startup configuration surface (scottleimroth-issue-19)

**Measurement and report:** [@scottleimroth](https://github.com/scottleimroth) (issue #19).
**Diagnostic and registry framing:** @Blackwellboy.

The original entry covers **request-surface** unvalidated control: the server
accepts invented or wrong request fields with HTTP 200. The same class has a
**startup-configuration** surface.

On a tested vLLM **0.26.0** image/checkpoint/backend combination on GB10/SM121,
`VLLM_FLASHINFER_MOE_BACKEND` was **unknown to the runtime**, never consumed by
the serving path, and had **no effect** on the resolved MoE backend. With the
variable removed and a fresh container, the engine still selected
`FLASHINFER_CUTLASS`. The config looked active; the engine silently ignored it.

### Distinguish

| Surface | Name | Shape |
|---|---|---|
| Request body | REQUEST_SURFACE_UNVALIDATED_CONTROL | invented JSON fields accepted |
| Startup env / launch | STARTUP_CONFIGURATION_UNVALIDATED_CONTROL | unknown `VLLM_*` env names ignored |

### Non-claims

- Not: all environment variables are ignored.
- Not: all vLLM versions behave this way.
- Not: CUTLASS is universally safe on GB10.
- Not: the observation applies to every checkpoint.

### The check (operator)

1. Enumerate configured `VLLM_*` environment names.
2. Compare with the actual runtime build's registered environment names.
3. Inspect unknown-variable warnings.
4. Inspect the resolved engine configuration.
5. Distinguish declared value from effective value.
6. Prefer `--fail-on-environ-validation` where the build supports it.

**Mitigation:** fail fast on unknown environment variables where supported.

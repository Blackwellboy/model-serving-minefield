# Playbook: porting a harness to a new server

Your harness measured correctly on one stack. You have now pointed it at
another one, and every request returns HTTP 200. That is not evidence of
anything. Eleven steps, in order.

Nothing here is new. Every step is a published entry, sequenced.

The rule the rest of this list is built on: **on a new server, every parameter
you send is a hypothesis rather than a setting** until you have shown the
server rejects a bad one.

---

## 1. Send a deliberately misspelled parameter and see whether you get a 400

**Guards:** [trap 77, one request field is validated and every other one you invent is accepted](../traps/reasoning/77-only-one-request-field-is-validated.md) (**Core**)

This is the first thing to run, because it decides how much every later step
is worth.

```bash
# 1. does the server even know this field?
curl -s localhost:11434/api/chat -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"hi"}],"enable_thinking":false,"stream":false,"options":{"temperature":0}}'
# 2. the same request with the field removed
curl -s localhost:11434/api/chat -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"hi"}],"stream":false,"options":{"temperature":0}}'
```

If the two responses are identical at temperature 0, the field did nothing.
If a misspelled parameter returns 200, the request surface is unvalidated,
**your own typos are silent too**, and a harness ported from another server
can measure its entire thinking-off arm on a thinking lane.

The registry names this the highest-operator-impact finding of its Ollama
coverage set, and it is reproducible in about two minutes.

## 2. Do not trust acceptance as evidence in either direction

**Guards:** [trap 07, `reasoning_effort` accepted and silently ignored](../traps/reasoning/07-reasoning-effort-silently-ignored.md), [trap 58, `reasoning_effort` injects a hidden preamble](../traps/reasoning/58-reasoning-effort-injects-hidden-preamble.md)

Grep the chat template for the parameter name **before** trusting any knob you
send. If the template never references it, the knob is dead on this build
regardless of what the server accepts. The general rule, in both directions:
diff the kwargs the template reads against the parameters the API accepts.

The inverse is also published, so do not over-learn "this field is inert":
on one measured lane `reasoning_effort` is an undocumented thinking switch
that also injects a hidden preamble.

## 3. Establish which reasoning field this server writes, per route

**Guards:** [trap 01, the reasoning field has two names](../traps/reasoning/01-reasoning-field-two-names.md) (**Core**)

```python
reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
```

Then confirm positively: send one prompt you are confident makes the model
think and assert the field is non-empty. An empty field means **wrong key** at
least as often as it means "did not reason".

For coding and answer extractors: **score only `content`**, never
`reasoning_content`. A harness that concatenates or executes reasoning text
as code is measuring the wrong channel. When comparing reasoning-control
arms, store the full request body and a hash of the server-rendered prompt
per row so a later audit can prove which directive actually landed
(Muse campaign note *(private evidence archived)*).

One published server carries **three** names and splits them by route
(`message.thinking` on one, a top-level field on another, `message.reasoning`
on the OpenAI-compatible route) and `reasoning_content` exists on none of
them. Enumerate the keys on each route you use, not once per server.

Also watch the shape, not just the name: on one stack an empty channel is an
**absent key**, not an empty string, so `msg["content"]` raises on every
thinking cap-hit and `msg.get("content", "")` converts a budget artifact into
"the model returned nothing".

## 4. Map the thinking toggle explicitly, and name the toggle this stack uses

**Guards:** [trap 03, `enable_thinking` default drift](../traps/reasoning/03-enable-thinking-default-drift.md) (**Core**), [trap 29, server thinking-off is not an off switch](../traps/reasoning/29-server-reasoning-off-is-not-an-off-switch.md), [trap 57, the kwarg is evaluated for truthiness](../traps/reasoning/57-thinking-kwarg-truthiness-coercion.md)

- Never reason about thinking from a template's default. Render your own
  prompt through the serving path and confirm which branch you landed in.
  Send the kwarg **explicitly** on every request and pin the revision.
- A server-side thinking-off flag can be a default rather than a gate, and a
  client kwarg overrides it. That is a budget hazard on a lane you sized for
  non-thinking output.
- Check for truthiness coercion. Post your message list to the tokenize route
  once with the kwarg as a JSON boolean `false` and once as the string
  `"false"`, and compare the final token of each render. If they differ, your
  lane coerces, and `"false"` turns thinking **on**.
- The spelling is per stack. One stack injects template kwargs server-side via
  a launch flag; another exposes `think` with several string values on its
  native route and `reasoning_effort: "none"` on its `/v1` route.

## 5. Prove tool calling end to end before you score anything agentic

**Guards:** [trap 19, one missing server flag turns structured tool calls into prose](../traps/tools/19-missing-jinja-breaks-tool-parsing.md) (**Core**), [trap 78, `tool_choice` is accepted and ignored](../traps/tools/78-tool-choice-accepted-and-ignored.md), [trap 26, a tool call inside an unclosed think block](../traps/tools/26-tool-call-inside-unclosed-think.md)

One request with one tool defined: assert a structured `tool_calls` array, not
prose describing a call. If you get prose, check the serve line for the
template and parser flags before touching the client.

Then check the gate in the other direction. On one measured stack
`tool_choice` is inert in both directions, so it **fails open** on the
standard way an agent framework suppresses a call:

```bash
curl -s localhost:11434/v1/chat/completions -H 'content-type: application/json' -d '{
  "model":"qwen3:8b","temperature":0,
  "messages":[{"role":"user","content":"What is the weather in Paris?"}],
  "tools":[{"type":"function","function":{"name":"get_weather",
    "parameters":{"type":"object","properties":{"city":{"type":"string"}}}}}],
  "tool_choice":"none"}' | grep -q '"tool_calls"' && echo "FAIL: tool_choice ignored"
```

Where it does not bind, the only control that works is **not sending `tools`
on that turn**.

Two failure modes at the other end of the same pipeline: raw markup appearing
alongside parsed calls, and a call emitted inside an unclosed think block that
the parser then eats, so the agent ends with `stop` while the raw text
contains a full tool call.

## 6. Establish the real ceiling behaviour at a real temperature

**Guards:** [trap 12, empty content at a token ceiling](../traps/evaluation/12-empty-content-at-token-ceiling.md) (**Core**), [trap 22, budget floors differ by size within a family](../traps/evaluation/22-family-card-budget-floors-differ-by-size.md)

Do not copy a token budget from the family card or from a sibling. There is no
single ceiling that makes empty-content-at-cap go away, and the published map
shows floors differing by **size within one family**. Bucket every scored zero
by "was content empty at a cap-hit", and re-run only those at a larger budget
before concluding anything about capability.

## 7. Treat launch flags as claims, not guarantees

**Guards:** [trap 32, the server `--max-tokens` flag is a per-request default](../traps/runtime/32-mlx-server-max-tokens-is-a-default-not-a-cap.md), [trap 79, an out-of-range context request is accepted](../traps/memory/79-out-of-range-context-request-accepted.md)

- Send one request with `max_tokens` greater than the server flag and read
  `usage.completion_tokens`. On one measured stack the flag is a per-request
  default, so a client runs straight past it. Put the clamp in a gateway you
  control, or size the lane for the largest value any client might send.
- Read the model's declared context before you set one, then assert you are
  under it. An out-of-range context request can return HTTP 200 with empty
  content and no clamp message. Do not raise the output budget to fix it.

## 8. Read the response, not the status code

**Guards:** [trap 77](../traps/reasoning/77-only-one-request-field-is-validated.md) (**Core**), [trap 16, finish_reason is not a failure signal](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md) (**Core**)

Every assertion in this playbook is on the response body. A 200 with
`finish_reason: stop` and a complete-looking answer can still be the wrong
arm, the wrong field, or an empty string.

## 9. Check the sampling defaults you inherited

**Guards:** [trap 21, no `generation_config.json` means the server's built-ins win](../traps/versioning/21-no-generation-config-server-defaults-win.md), [trap 17, per-arm recommended sampling](../traps/evaluation/17-per-arm-recommended-sampling-confound.md) (**Core**)

Compare what the live server reports as its defaults against the checkpoint's
shipped `generation_config.json`. If the checkpoint ships none, read the
card's prose recommendation instead, note which **mode** it is for (thinking
and non-thinking recommendations differ), and set sampling explicitly on every
request. Never describe a run as "at model defaults" for a checkpoint that
ships no generation config.

## 10. Check whether the parser is between you and your timings

**Guards:** [trap 80, a reasoning parser batches the SSE stream](../traps/runtime/80-reasoning-parser-batches-sse-deltas.md), [trap 23, the streamed answer lands in the reasoning channel](../traps/reasoning/23-streaming-answer-lands-in-reasoning-channel.md)

If you time from stream deltas, a reasoning parser sitting in the path can
batch the stream, so your delta timings describe its flush schedule rather
than the lane. And if streamed replies come back blank while non-streamed are
fine, the answer is being routed into reasoning deltas with `content` empty.

## 11. Do not call the lane up until it has generated

Readiness is a completed generation, not an endpoint answering. `/v1/models`
responds as soon as the HTTP server binds, which on a large checkpoint is
minutes before it can generate. A poll gated on that route reports a
connection refusal or a 200 depending on timing, and neither is readiness.
Details:
[doctor/README.md](../doctor/README.md#readiness-is-a-completed-generation-not-an-endpoint-answering).

---

**Per-stack shortcuts.** [vLLM](../stacks/vllm.md) ·
[llama.cpp and GGUF](../stacks/llama-cpp.md) · [Ollama](../stacks/ollama.md) ·
[mlx_lm](../stacks/mlx.md).

**Related playbooks.**
[Thinking died when I made it multi-turn](thinking-died-multi-turn.md) once
requests are landing correctly.
[Before you publish an A/B](before-you-publish-an-ab.md) before the ported
harness produces a number anyone reads.

# Trap 78: `tool_choice` is accepted and ignored, and it fails open

**Found by Blackwellboy.**

**Status: reproduced here**, 2026-07-28, on Ollama 0.32.5 with `qwen3:8b`,
on both the native `/api/chat` route and the OpenAI-compatible
`/v1/chat/completions` route. Runnable against any install of that stack with
the two requests below; both the server and the model are free to obtain.

**Symptom.** Your agent framework gates a turn by sending
`tool_choice: "none"`, because that is the standard way to say "answer in
prose this turn, do not call anything". The model calls a tool anyway. On the
OpenAI-compatible route it comes back with `finish_reason: "tool_calls"`, which
is the server telling you plainly that it did the thing you told it not to do.

No warning, no error, no field in the response indicating the parameter was
dropped.

**Mechanism.** The parameter is parsed off the request and not applied. It fails
in **both** directions, which is worth stating because a reader who has only
seen one half will assume the other half works:

| Sent | With | Observed |
|---|---|---|
| `tool_choice: "none"` | a prompt that invites a call | a tool call, on both routes, `finish_reason: tool_calls` on `/v1` |
| `tool_choice: "required"` | a prompt with no tool need | plain prose, no call, on both routes |

So it is not "none is unsupported": the whole parameter is inert. What decides
whether a call happens is the presence of the `tools` payload and the model's
own judgement, and nothing you send alongside it.

**The failure is open, not closed, and that is the part that matters.** A gate
that fails closed produces a visible outage and gets fixed in an hour. This one
produces an agent that occasionally takes an action on a turn its author
believed was read-only. In a loop with a side-effecting tool, that is not a
degraded response, it is an unintended write.

**A second, smaller thing found in the same probe.** An invalid tool *schema*,
in syntactically valid JSON, returns

```
{"error":"Value looks like object, but can't find closing '}' symbol"}
```

which is a JSON-syntax message for a schema-validity problem. If you get that
error and your JSON parses locally, stop looking at your brackets and look at
whether your schema is well-formed as a schema.

**Stacks and builds bitten.** Ollama 0.32.5, `/api/chat` and
`/v1/chat/completions`, `qwen3:8b`, GB10 aarch64 CUDA 13.

**The check.** Send the same tool-inviting prompt twice, once with
`tool_choice: "none"`, and look at what came back rather than at the status:

```bash
# expect: no tool call. Assert it.
curl -s localhost:11434/v1/chat/completions -H 'content-type: application/json' -d '{
  "model":"qwen3:8b","temperature":0,
  "messages":[{"role":"user","content":"What is the weather in Paris?"}],
  "tools":[{"type":"function","function":{"name":"get_weather",
    "parameters":{"type":"object","properties":{"city":{"type":"string"}}}}}],
  "tool_choice":"none"}' | grep -q '"tool_calls"' && echo "FAIL: tool_choice ignored"
```

Generalise it: for every request parameter your agent relies on as a **safety
gate**, write one probe that would fail if the parameter were dropped, and run
it against each server you deploy on. A gate you have not tried to defeat is a
gate you are assuming.

**The fix.** To suppress calls on this stack, **do not send `tools` on that
turn.** That is the only control that works here, it works everywhere, and it
does not depend on the server implementing anything. Keep `tool_choice` for
servers where you have proven it binds.

**Found.** 2026-07-28, during first-party Ollama coverage.

**Attribution.** Blackwellboy. Related:
[trap 19](19-missing-jinja-breaks-tool-parsing.md) for the other end of the
same pipeline, where a call is made and not parsed.

## Added 2026-08-11: Muse / llama.cpp - forced **named** tool choice ignored; required/auto effective

**Muse Glimmer 30B, llama.cpp OpenAI-compatible tools path (bounded API matrix).** On the tested pin: `tool_choice=auto` and `tool_choice=required` behaved as effective; a **forced named** tool choice was **silently ignored** in the tested case; `tool_choice=none` was a weak/rejected path rather than a clean off switch. This is not a full reproduction of the Ollama both-directions failure above, but it is the same operator class: **do not treat request acceptance of `tool_choice` as semantic parity** - assert the tool actually selected.

*Status of this addendum: measured here, raw not published; single-path matrix.* See private evidence archive *(private evidence archived)*.

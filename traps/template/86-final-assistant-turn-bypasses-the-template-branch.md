# Trap 86: the final assistant message is not rendered by the template's assistant branch, so a prefilled turn is delimited differently from the same text mid-conversation

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, on a Mistral-family Q8_0 GGUF of
unstated provenance, llama.cpp `b9878-2da668617`, `--jinja`. Renders taken from
the server's own `/apply-template`.

**Symptom.** Assistant prefill (ending the message list on an assistant turn so
the model continues it) produces subtly different behaviour from the same text
appearing mid-conversation, and a prefilled turn never shares a prefix with the
completed conversation it becomes one request later.

**Mechanism.** For a message list ending on an assistant turn, the server does
not run that message through the template's assistant branch. It renders
everything up to it and appends the assistant `content` raw. The template's
assistant branch is:

```
{{- " " + message["content"]|trim + eos_token}}
```

which contributes a leading space and a trailing end-of-sequence token. The
prefill path contributes neither. Measured, same `A1`, same lane:

| messages | rendered |
|---|---|
| `system, user(U1), assistant(A1)` (A1 last) | `[INST] SYS\n\nU1[/INST]A1` |
| `system, user(U1), assistant(A1), user(U2)` (A1 mid) | `[INST] U1[/INST] A1</s>[INST] SYS\n\nU2[/INST]` |

`[/INST]A1` versus `[/INST] A1`. One space, which is a different token
boundary, on a byte the model saw with the space during training.

**The corollary that costs money.** Because the prefill path appends raw
content, an assistant message whose `content` is `null` and which carries only
`tool_calls` renders to **nothing at all**: the render of
`user, assistant(tool_calls)` is byte-identical to the render of `user` alone.
HTTP 200, no warning. See the tool round-trip entry.

**Check it.** Send the same assistant text in last position and in
second-to-last position to `/apply-template` and diff the two strings around
it. If the delimiters differ, your prefill is not the conversation your
multi-turn arm produces, and the two will not share a cache prefix.

**Scope.** One Mistral-family Q8_0 GGUF of unstated provenance on llama.cpp
`b9878`. The mechanism is a server-side prefill path, so it should travel
across templates on this build; the exact delimiters are a property of this
template.

**Found.** 2026-07-28.

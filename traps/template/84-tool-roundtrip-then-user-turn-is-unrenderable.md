# Trap 84: a completed tool round trip followed by a user turn is unrenderable, and the 400 blames the template rather than your message list

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, on a Mistral-family Q8_0 GGUF of
unstated provenance, llama.cpp `b9878-2da668617`, `--jinja`.

**Symptom.** An agent loop works for exactly one tool call and then dies. The
model calls the tool, your framework appends the tool result and the user's
next message, and the very next request returns HTTP 400 with a message about
template parser generation. Nothing in the error names your message list, so
the first three hours go into the template and the serve flags.

**Mechanism.** The template guards role alternation, and deliberately exempts
tool traffic from the counter:

```
{%- if not (message.role == "tool" or message.role == "tool_results"
            or (message.tool_calls is defined and message.tool_calls is not none)) %}
    {%- if (message["role"] == "user") != (ns.index % 2 == 0) %}
        {{- raise_exception("... roles must alternate user/assistant/user/assistant/...") }}
    {%- endif %}
    {%- set ns.index = ns.index + 1 %}
{%- endif %}
```

The exemption skips the assistant turn that carried the tool call. So the
counter never advances across the tool exchange, and the *next* user message
lands on odd parity and raises. The guard was written to let tool traffic
through and instead makes the ordinary agent loop unreachable.

Measured, one tool defined, ids of the required length throughout:

| message sequence | result |
|---|---|
| `user` | 200 |
| `user, assistant(tool_calls)` | 200 (see the note below) |
| `user, assistant(tool_calls), tool` | 200, renders `[TOOL_CALLS]` and `[TOOL_RESULTS]` |
| `user, assistant(tool_calls), tool, user` | **400** |
| `user, assistant(tool_calls), tool, assistant, user` | 200 |

The fourth row is the shape every agent framework produces. The fifth row is
the workaround: an assistant text turn between the tool result and the next
user message restores parity.

**Two secondary tells worth their own attention.**

*The error text points at the wrong thing.* Every render-time
`raise_exception` in this template surfaces as:

```
Unable to generate parser for this template. Automatic parser generation failed:
... Error: Jinja Exception: After the optional system message, conversation roles must alternate ...
```

The headline says parser generation; the cause is the message list you sent.
The same headline appears for a genuinely malformed template. Read past the
first line to the `Jinja Exception:` line, which is the real one.

*The row-two 200 is silent data loss.* An assistant message carrying only
`tool_calls`, in last position, renders **byte-identical** to omitting it
entirely: the tool call does not appear in the prompt. The server returns 200
and never mentions it. Any code that replays a truncated history ending on a
tool call is silently dropping it.

**Check it.** Send the four-message sequence in row four to `/apply-template`.
If it 400s, your agent loop needs the intervening assistant turn.

**Adjacent negative, recorded on purpose.** On this stack, tool-call
`arguments` supplied as a **JSON string** rendered identically to `arguments`
supplied as an **object** (`"arguments": {"city": "Paris"}` in both cases): the
server normalises before the template sees it, and `/props` advertises
`chat_template_caps.supports_object_arguments: true`. The string-versus-object
dialect split that bites elsewhere did **not** bite here. The template's own
9-character tool-call id rule is real and does fire (`Tool call IDs should be
alphanumeric strings with length 9!`), but only in the sequences that survive
the alternation guard.

**Scope.** One Mistral-family Q8_0 GGUF of unstated provenance on llama.cpp.
The alternation-plus-exemption shape is the portable part; check your own
template for it.

**Found.** 2026-07-28.

# Trap 82: the template moves the system prompt to the LAST user turn, so the prefix changes every turn

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, on a Mistral-family Q8_0 GGUF of
unstated provenance served on llama.cpp `b9878-2da668617` with `--jinja` and
the checkpoint's own embedded template. Every render below is the server's own
`/apply-template` output, not a local Jinja re-implementation.

**Evidence pointer.** One request to `/apply-template` on the reader's own
lane, with a three-message history. No files from us are needed.

**Symptom.** A multi-turn chat lane reports near-zero prefix-cache reuse. Each
turn re-prefills the whole conversation even though only the newest user
message was appended. Latency grows linearly with turn count and the cache-hit
counter stays at zero, which reads like a broken cache rather than a template
property.

**Mechanism.** The template does not emit the system message where it was
supplied. It hoists the system text and re-attaches it to whichever user
message is currently last:

```
{%- if loop.last and system_message is defined %}
    {{- "[INST] " + system_message + "\n\n" + message["content"] + "[/INST]" }}
```

So the system block physically migrates forward one turn at a time. Measured,
with `SYS` standing in for the system content:

| messages sent | rendered prompt |
|---|---|
| `system, user(U1)` | `[INST] SYS\n\nU1[/INST]` |
| `system, user(U1), assistant(A1), user(U2)` | `[INST] U1[/INST] A1</s>[INST] SYS\n\nU2[/INST]` |

Turn 1 puts `SYS` at byte 7. Turn 2 puts `SYS` after `A1`, and the turn-1
prefix `[INST] SYS\n\nU1[/INST]` no longer occurs anywhere in the turn-2
prompt. The two prompts share no common prefix beyond `[INST] `, so the
longest-common-prefix cache has nothing to reuse.

This is not a caching bug. The cache is working exactly as specified; the
template has arranged for there to be no shared prefix.

**Why it is easy to miss.** Every single-turn probe looks perfect: the system
prompt renders, the reply obeys it, the cache reports a hit on an immediate
repeat of the same request. The reuse collapse only appears once a real
conversation grows, by which time the cache is usually blamed.

**Check it in one request.**

```bash
curl -s localhost:PORT/apply-template -H 'Content-Type: application/json' -d '{
  "messages":[{"role":"system","content":"SYS"},
              {"role":"user","content":"U1"},
              {"role":"assistant","content":"A1"},
              {"role":"user","content":"U2"}]}'
```

If `SYS` comes back next to `U2` rather than at the head of the string, this
lane cannot share a prefix across turns. Confirm the consequence with two
sequential chat requests and read `prompt_tokens_details.cached_tokens`.

**Scope.** Measured on one Mistral-family Q8_0 GGUF of unstated provenance,
served on llama.cpp. The behaviour is a property of the embedded template, so
expect it wherever this template shape travels, and expect it NOT to hold for
templates that emit the system block once at the head. We make no claim about
Mistral checkpoints generally, about any named model, or about any product.

**Found.** 2026-07-28, first coverage pass on this file.

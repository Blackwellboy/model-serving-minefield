# Trap 83: the chat template carries a hard-coded default system prompt, injected whenever the request omits one

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, on a Mistral-family Q8_0 GGUF of
unstated provenance, llama.cpp `b9878-2da668617`, `--jinja`.

**Evidence pointer.** Two `/apply-template` requests on the reader's own lane:
one with a system message, one without. Compare the rendered lengths.

**Symptom.** A lane behaves as though a system prompt is set when the client
sends none. Evaluations that deliberately run "no system prompt" as a control
arm are not running a control arm. A/B comparisons between "default" and "our
system prompt" are comparing two system prompts, not one against none.

**Mechanism.** The template's `else` branch does not set the system message to
empty; it assigns a literal block of prose:

```
{%- if messages[0]["role"] == "system" %}
    {%- set system_message = messages[0]["content"] %}
{%- else %}
    {%- set system_message = "<a 388-character persona paragraph literal>" %}
{%- endif %}
```

Because `system_message` is assigned in **both** branches, the later guard
`{%- if loop.last and system_message is defined %}` is always true, so the
injected text is always emitted. Measured on this file: omitting the system
message renders 388 characters of template-supplied prose ahead of the user
content, and the reply demonstrably follows it.

We do not reproduce the injected text here. Its content is a property of one
unlabelled checkpoint and is not the finding; the finding is that a template
can inject a non-empty default at all, silently, with a 200.

**Why it is easy to miss.** Nothing in the request, the response, or the usage
block mentions it. `prompt_tokens` rises by the length of the injected text,
which is the only tell in a normal response body, and nobody reads
`prompt_tokens` on a control arm.

**Check it in two requests.**

```bash
curl -s localhost:PORT/apply-template -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"X"}]}'
curl -s localhost:PORT/apply-template -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"system","content":""},{"role":"user","content":"X"}]}'
```

If the first render is materially longer than the second, your no-system-prompt
arm has a system prompt. Sending an explicit empty system message is the
workaround on this template, because the `if` branch then assigns the empty
string.

**Scope.** One Mistral-family Q8_0 GGUF of unstated provenance. A template is
free to do this and some do; the class is "read the template's else branch
before calling any arm a control".

**Found.** 2026-07-28.

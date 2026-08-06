# Trap 66: the template scans user text for a toggle, obeys it, and deletes it

**Found by Blackwellboy.**

**Status: reproduced here with matched controls in both directions.**

**Symptom.** A file path in your prompt comes back wrong. Not paraphrased,
**missing a directory component**, and the model answers as if that component was
never there. Separately, and often in the same request, the reasoning mode is the
opposite of what you asked for: you sent `enable_thinking: false` and the
response carries a reasoning trace, or you sent `true` and it does not.

**Mechanism.** The chat template scans every user and system message, including
the text parts of a multimodal message, for the literal substrings `/think` and
`/no_think`. Either one overrides the `enable_thinking` keyword that the card
documents as the way to control reasoning. The card never mentions the
substrings.

The same pass then **deletes both substrings from the message before the model
sees it**. The user does not have to be trying to toggle anything. Any ordinary
path, URL, or sentence containing the character sequence is enough, and the
deletion is silent.

Request carried `enable_thinking: false`:

```
request text : Open the file src/think/main.py and summarise it.
rendered text: Open the file src/main.py and summarise it.
generation tail: <|im_start|>assistant\n<think>\n      <- reasoning ON, opposite of the request
```

Mirror case, request carried `enable_thinking: true`:

```
request text : Explain the module at src/no_think/util.py.
rendered text: Explain the module at src/util.py.
generation tail: <|im_start|>assistant\n<think></think>  <- reasoning OFF, opposite of the request
```

Prose is enough: `Compare and/think versus and/no_think as strings.` renders as
`Compare and versus and as strings.`

**Controls.** `src/reason/main.py` in the same request shape renders the path
intact and ends `<think></think>`, reasoning off as requested. So the effect is
specific to the two magic substrings and is not a general path-mangling bug.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Nano Omni 30B A3B Reasoning
NVFP4, vLLM 0.20.0 upstream arm64 container, single GB10-class node, reasoning
parser `nemotron_v3`. Verified through `POST /tokenize` with per-token strings,
so the corruption is visible in the assembled prompt rather than inferred from
the answer.

**Not yet checked elsewhere.** The two text-only siblings in the same family were
not probed for this. A `grep` of their chat templates for the literal strings
settles it offline, with no lane, and is the first thing anyone extending this
should do.

**The check.** Send a prompt containing `/think` or `/no_think` as part of an
ordinary path, with the opposite `enable_thinking` keyword. Render the prompt and
compare it to what you sent, character for character. Then check which way the
generation prompt ends.

Cheaper still, and offline: `grep -c "/no_think" chat_template.jinja` next to the
weights. Any hit means your users' text is being scanned.

**The fix.** There is no server-side switch for this. Client-side:

1. Escape or reject the substrings in user-supplied text before sending, or send
   the affected text as a quoted block the template does not scan (verify by
   rendering; do not assume).
2. Do not rely on `enable_thinking` alone to establish which arm you measured.
   Assert on the response: an arm you believe is thinking-off must have an absent
   or empty reasoning field, per request, not per configuration.
3. If your corpus contains file paths, URLs or code, assume some fraction of it
   is being silently rewritten and check before reporting anything about
   instruction following or retrieval accuracy on it.

**If you miss it.** Two failure modes, and they compound. Your prompts are not
the prompts you think you sent, so any result about path handling, code
comprehension or verbatim reproduction is measured on mutated input. And your
thinking-on and thinking-off arms are contaminated by an unknown number of rows
that ran in the other mode, which turns a capability comparison into noise with a
plausible mean. When the two disagree in one particular direction the answer is
lost entirely, which is a separate entry.

**Negatives recorded.**

- A control substring (`/reason`) is not scanned and not deleted.
- The deletion applies to the text the model sees, not to the response echo, so a
  client that logs its own outbound request will see the original and find
  nothing wrong.

**Related.** [trap 03](../reasoning/03-enable-thinking-default-drift.md), the
documented toggle whose behaviour this overrides;
[trap 07](../reasoning/07-reasoning-effort-silently-ignored.md), accepted-but-not-read
kwargs, of which this is the inverse case: a control that is read but never
declared. The answer-loss consequence is a separate draft,
[answer-lands-in-reasoning-on-toggle-conflict](../reasoning/64-answer-lands-in-reasoning-on-toggle-conflict.md).

**Found.** 2026-07-27, first multimodal lane characterised in this line of work.

**Attribution.** Blackwellboy.

## The mirror case: injection, on Ollama

The entry above is a template that **scans for the marker and deletes it**.
There is a second shape of the same mechanism, and it is the opposite
operation: a template that **appends the marker and lets it leak into the
answer**. Same idea, same last-user-message target, opposite direction, and it
damages a different thing.

**Ollama 0.32.5 with the qwen3 template, `qwen3:8b`, GB10 aarch64 CUDA 13.**
When thinking is active the template appends a literal marker to the **last
user message**:

```
{{- if and $.IsThinkSet (eq $i $lastUserIdx) }}{{ if $.Think }}{{" "}}/think{{ else }}{{" "}}/no_think{{ end }}{{ end }}
```

Asked `"Reply with exactly: OK"` at temperature 0:

| arm | content |
|---|---|
| `think: true` | `"OK /think"` <- **the marker is in the answer** |
| *(think absent)* | `"OK /think"` <- **also leaked** |
| `think: false` | `"OK"` |

Reproduced on four separate `num_predict` settings.

**The leak is not reliably introspectable**, which is the part that wastes an
afternoon: asked to echo its own message back verbatim, the model returned it
**without** the marker, in both arms. So the obvious diagnostic, asking the
model what it received, actively tells you nothing is wrong.

**Consequence.** Exact-output evaluation, string-equality assertions and
diff-based scoring are all contaminated by a token the operator never sent. A
harness scoring `"OK"` against `"OK /think"` records a failure that is entirely
the template's.

**The fix on this half.** Strip a trailing ` /think` or ` /no_think` before
scoring, or send `think: false` where the workload allows it. As with the
deletion half: render, compare against what you sent character for character,
and do not trust the model's account of its own input.

*Status of this addendum: reproduced here. The template is public, the marker
is one grep, and the leak is one temperature-0 request.*

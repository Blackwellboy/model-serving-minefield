# Trap 56: the checkpoint ships no chat template, and the one you get is Python

**Found by Blackwellboy.**

**Status: reproduced here** on a live two-node DeepSeek-V4-Flash lane,
2026-07-28. Every render below was pulled from the running server's own
`/tokenize` endpoint with `return_token_strs`, so it is what the model
actually received, not what a local library predicted.

**Evidence pointer**, since reproduced here requires one a stranger can act on:
the finding is structural and it is checkable against the public checkpoint
without touching our lane. Fetch the repository and confirm there is no
`chat_template.jinja` and no `chat_template` key in `tokenizer_config.json`,
then read the Python encoder module it ships instead. That is a public source
file, and it is the thing this entry is about.

**Symptom.** You follow the standard advice for template forensics: pull the
chat template out of the checkpoint, hash it, render it locally, and compare
against what the server does. On this model family every one of those steps
fails at step one. There is no `chat_template.jinja` in the checkpoint, and
`tokenizer_config.json` has no `chat_template` key. A tool that expects to find
a template concludes either "no template, this model cannot chat" or, worse,
falls back to a generic default and reports success. Meanwhile the server is
happily serving chat completions with a template you have not read.

**Mechanism.** The template is not data, it is **code**. The checkpoint carries
a Python encoder module, and the server is launched with a tokenizer mode that
names this family plus `--trust-remote-code`. Prompt construction happens in
that module: role markers, the tool preamble, the thinking toggle, and the
reasoning-effort text are all Python string assembly, not Jinja. Consequences
that matter in practice:

- **There is nothing to hash.** "md5 the template" produces nothing. What you
  must hash instead is the encoder source file in the checkpoint. On our
  checkpoint that file is 27,908 bytes; it is the artifact that determines
  prompt shape, and it is the one a re-upload can silently change.
- **A different serving stack gives you a different prompt.** Anything that
  cannot execute the checkpoint's Python, or that runs it at a different
  revision, builds a different prompt from the same messages. This is the same
  hazard as [trap 24](24-official-template-breaks-cpp-jinja.md), one layer
  further down: there, the template is Jinja that only Python can evaluate;
  here, there is no template at all.
- **`trust_remote_code` is load-bearing for correctness, not just for loading.**
  Turning it off does not degrade politely.

**The renders, and three things in them worth knowing.** With a single user
message the server produces:

```
<BOS><|User|>Q<|Assistant|></think>
```

*One.* **Thinking-off is implemented as a pre-filled closing tag.** The
generation prompt ends with a closing think tag already emitted, so the model
begins its turn already outside a reasoning block. Flip the thinking kwarg and
the same position holds an opening tag instead. This is the mechanism behind
the stray-close-tag family in [trap 02](02-orphaned-think-close-tag.md), except
here it is intended behaviour, and a client-side parser that strips a leading
close tag is removing something the server put there on purpose.

*Two.* **There is no system role marker at all.** A system message is
concatenated raw ahead of the first user marker:

```
<BOS>S<|User|>Q<|Assistant|></think>
```

Nothing delimits it, labels it, or closes it. Two system messages concatenate
with no separator between them, rendering `S1S2` as one run of text. That is
merely ugly. The damaging case is a system message that is not first:

```
messages: [user "Q", system "LATESYS", user "Q2"]
renders:  <BOS><|User|>QLATESYS<|User|>Q2<|Assistant|></think>
```

The late system message is glued onto the end of the **user's** content with no
separator. It does not become a weak instruction; it becomes an invisible
suffix of what the user said. Any framework that appends a system message for
guardrails, tool hints or a date stamp after the conversation has started is
silently editing the user's turn. Nothing errors, and the request returns 200.

*Three.* **Tool definitions are injected at the top, in the same slot.** With
tools present, a roughly 250-token preamble describing an XML-shaped markup
dialect is prepended, and the system message lands **after** it, again with no
delimiter. Tool results come back as a plain-text tag inside a user turn rather
than a distinct role, and a following user message is merged into that same
turn. Note the asymmetry: tool **calls** use reserved special tokens, tool
**results** use ordinary text. Text a user can type. If you pass user content
through to this template unescaped, a user can write a tool result.

**The check.** Do not read the checkpoint; ask the server what it built. Run it
for four cases: user only; system plus user; a system message placed **after** a
user message; and a conversation carrying tools. If the second and third produce
the same shape of thing, you have a role marker. If the third silently welds the
system text onto the user's, you have this trap. Separately, hash the
checkpoint's encoder module and record the hash next to your results, because
that file, not a template, is what a re-upload changes.

**Which endpoint you render on matters, and this bit cost us a wrong
conclusion.** This server exposes two render surfaces that do not agree.
`/tokenize` with `return_token_strs` is convenient and is faithful for
`messages`, `tools` and `chat_template_kwargs`. It is **not** faithful for
top-level request fields, because anything outside its own request schema is
silently discarded: we had `reasoning_effort` rendering as a no-op on
`/tokenize` while the same body on `/v1/chat/completions` injected
seventy-nine tokens and switched reasoning on (see
[trap 58](../reasoning/58-reasoning-effort-injects-hidden-preamble.md)).
Prefer `/v1/chat/completions/render` where it exists, since it reproduces the
real mapping. Where it does not exist, fall back to comparing `prompt_tokens`
on real completions, which cannot be faked by a schema mismatch. A
tokenize-only preflight will report a false clean for any trap that lives in a
top-level parameter.

**The fix.** Three practical rules on a stack like this. Put every system
instruction in the first message, always, and merge them yourself so you can
see the join rather than discovering it. Never append a system message
mid-conversation; fold it into the next user turn deliberately, where you
control the separator. And treat the encoder module hash as part of your
model's identity in your run records, the way you would treat a template hash
elsewhere.

**Stacks and builds bitten.** vLLM `0.21.1rc1.dev339+g1967a5627bc3` serving a
community-abliterated DeepSeek-V4-Flash checkpoint, tokenizer mode
`deepseek_v4`, `--trust-remote-code`, tensor parallel 2 across two DGX Spark
GB10 nodes. The no-template-file structure and the Python encoder come from the
checkpoint, so they are properties of the model family as packaged; the exact
renders above are from this build and this server version.

**Found.** 2026-07-28, first registry coverage pass on this lane.

**Attribution.** Blackwellboy. Related:
[trap 24](24-official-template-breaks-cpp-jinja.md) (templates that only one
runtime can evaluate), [trap 02](02-orphaned-think-close-tag.md) (stray close
tags), [trap 30](30-default-system-message-silently-replaced.md) (system
message not surviving the template intact).

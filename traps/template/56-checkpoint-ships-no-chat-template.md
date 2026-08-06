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

## Corroborated upstream 2026-07-28: vllm#46710

[vllm#46710](https://github.com/vllm-project/vllm/issues/46710)
([@wqh17101](https://github.com/wqh17101),
[@bbrowning](https://github.com/bbrowning),
[@lazypool](https://github.com/lazypool),
[@felix0080](https://github.com/felix0080)) reports the operator-visible
consequence of this entry's template property, from the serving-default
direction. Credit for that report is theirs. **Status of this section: reported
by others**; we have not reproduced the default they hit.

Their matrix has the same shape as the check above: a model whose template
raises returns HTTP 400 on a late system message, and this checkpoint returns
200 with degraded output because its template renders happily. The thread
attributes the degradation to attention decay across a sliding window. **The
render in this entry says it is simpler and more mechanical:** there is no
system message in that position for attention to weight at all, because the
text was concatenated onto the end of the user's turn before the model saw
anything. That accounts for the reported overwriting of the user's query, for
why the same payload is clean on checkpoints that do have a system role marker,
and for the intermittency, without appealing to the attention window.

The two findings are complementary. This entry is a **template property** that
has been true of this checkpoint all along. The issue is about a **serving
default that made it reachable**: vLLM moved from merging system messages to
the front toward preserving them in place, for prefix-cache reasons, with
auto-detection that treats "the template rendered without raising" as "the
model handles this". For a checkpoint with no system role marker, rendering
without raising is exactly what it will do.

[PR #47681](https://github.com/vllm-project/vllm/pull/47681) proposes flipping
the default back to merge, with an opt-in allowlist that starts empty. **As of
2026-07-28 it is open, unmerged, and its changes land in the Anthropic
entrypoint**, so it is not a fix you can assume is in your build, and it is
scoped narrower than the general chat path.

**Scope, stated because our own lane cannot show this half.** We serve a
lineage that predates those defaults, so we have not observed preserve-in-place
ourselves. We established the template property directly from `/tokenize`; the
upstream thread supplies the evidence that a current default makes it bite.
Neither half is derived from the other.

## Pinned source and render boundary, 2026-07-30

[@wqh17101](https://github.com/wqh17101) supplied a cross-model source map,
immutable pins, and explicit permission to publish it with credit in
[this issue comment](https://github.com/vllm-project/vllm/issues/46710#issuecomment-5131158274).
That contribution is source-level corroboration. It does not replace or take
credit for Blackwellboy's original live `/tokenize` finding above.

The source check is pinned to vLLM
[`48a077e4cfaa5425ac5df67ce95f07a99c6d26d5`](https://github.com/vllm-project/vllm/tree/48a077e4cfaa5425ac5df67ce95f07a99c6d26d5)
and DeepSeek-V4-Flash
[`60d8d70770c6776ff598c94bb586a859a38244f1`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash/tree/60d8d70770c6776ff598c94bb586a859a38244f1).
The loading distinction matters:

- The upstream `encoding/encoding_dsv4.py` is 27,908 bytes with SHA-256
  `bdbd57c132a1b3725042323d02b98b9d1df28e5f388f134399555d041f5055e0`.
  Its tokenizer config has no `auto_map` and no ordinary chat template.
- vLLM therefore routes `DeepseekV4Tokenizer.apply_chat_template` through its
  maintained `vllm/tokenizers/deepseek_v4_encoding.py` copy. At the pinned
  vLLM revision that file has SHA-256
  `20eb61abe97be7607fd12e2b929faef91743cd2699ad9a4e032b54237d137694`.
  Its canonical LF Git content has MD5
  `70a8bab597ddab53ab8d0bf60b4230ec`; the contributor-supplied
  `4e671e9adc64ca315db284545e72a6db` is the same bytes checked out with CRLF
  line endings.

This gives the three-way comparison without broadening this trap's subject.
The existing DeepSeek endpoint render is `WELDED_TO_USER`. Pinned Jinja
execution for GLM-5.1, GLM-5.2, and Kimi-K2.6 is `ROLE_MARKED`. Pinned Jinja
execution for MiniMax-M2.5, M2.7, and M3 is `DROPPED`, meaning non-welding but
lossy, not safe. The broader failure class and runnable generic check now live
in [trap 113](113-inline-system-role-is-not-a-stable-contract.md).

Kimi-K3 is a useful loading-path contrast, not evidence for this trap.
Revision
[`9f62e4e9fffbd0a83ddd60e1c209d828994b3569`](https://huggingface.co/moonshotai/Kimi-K3/tree/9f62e4e9fffbd0a83ddd60e1c209d828994b3569)
exposes `tokenization_kimi.TikTokenTokenizer` through `auto_map`; vLLM's
Kimi-K3 renderer at the pinned source revision delegates to that upstream
tokenizer rather than maintaining an encoder copy. The isolated CPU tokenizer
execution is preserved, but its rendered string and token-ID decode differ in
spacing around structural tokens, so the strict result is `INCONCLUSIVE`.
The actual Kimi-K3 vLLM endpoint remains `UNDER_TEST`.

| Claim | Evidence surface | Boundary |
|---|---|---|
| DeepSeek inline system text is welded into the user span | `ENDPOINT_RENDER_REPRODUCED` | Original live lane and build above |
| DeepSeek upstream and vLLM Python encoders share the unmarked system path | `SOURCE_INSPECTED_AT_PINNED_REVISION` | Exact revisions and hashes above |
| Cross-model Jinja behavior | `TEMPLATE_EXECUTED_AT_PINNED_REVISION` | Generic Transformers template execution, not a checkpoint tokenizer or serving endpoint |
| Kimi-K3 upstream tokenizer load and render | `TOKENIZER_EXECUTED_AT_PINNED_REVISION` | Isolated tokenizer only; cross-representation result `INCONCLUSIVE` |
| Kimi-K3 vLLM `/tokenize` behavior | `UNDER_TEST` | No endpoint reproduction in this pass |
| OpenAI versus Anthropic entrypoint behavior | `INCONCLUSIVE` | Source paths inspected; no endpoint pair reproduced |

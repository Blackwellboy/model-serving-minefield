# Trap 67: the server normalises message content to a list and the template renders the list

**Found by Blackwellboy.**

**Status: reproduced here, per-token, with a positional control.**

**Symptom.** Multi-turn quality is worse than single-turn in a way that does not
look like context length. The model starts answering in an odd style, sometimes
literally in Python list syntax. Prefix-cache hit rates are worse than the
conversation structure suggests. Nothing in the API response shows anything
wrong, and the request you sent is well formed.

**Mechanism.** On a multimodal server, message content is normalised from a
string into a list of content parts before rendering, so that text and media can
be handled uniformly. The chat template then tests `content is string`, that test
fails, and the list object is rendered into the prompt through string coercion.

The prompt therefore contains **Python object syntax**:

```
<|im_start|>assistant
[{'type': 'text', 'text': 'PLAIN_ANSWER_ONE'}]<|im_end|>
```

With a think block in the prior turn, the template's own splitting leaves a
dangling fragment of the repr behind:

```
<|im_start|>assistant
<think></think>VISIBLE_ANSWER_TWO'}]<|im_end|>
```

Note the orphaned `'}]`. The template consumed the front of the repr and left the
back.

**Positional control.** The **first** system message is affected the same way; a
system message that is **not** first renders correctly:

```
<|im_start|>system
[{'type': 'text', 'text': 'SYS_ONE'}]<|im_end|>
...
<|im_start|>system
SYS_TWO<|im_end|>
```

That asymmetry is what makes this a template-path bug rather than a blanket
normalisation. It also means a two-message probe can miss it entirely.

**Why it is worse than token waste.** The model is being shown quoting, bracket
and dictionary-key noise attributed to itself, on every prior turn, as an example
of how it speaks. A downstream symptom was visible in a probe: asked to list
chart labels after an image turn, the model replied
`['Alpha', 'Bravo', 'Charlie', 'Delta']`, in the repr style the corrupted history
had been demonstrating to it. Prefix caching then stores the corruption, so the
cost is paid again on every continuation.

**It fires unconditionally.** There is no trigger, no kwarg, and no opt-out. Any
conversation with at least one prior assistant turn is affected.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Nano Omni 30B A3B Reasoning
NVFP4, vLLM 0.20.0 upstream arm64 container, single GB10-class node. Verified
through `POST /tokenize` with `return_token_strs: true`: the per-token strings
contain `[{`, `'`, `type`, `':` as literal prompt tokens, so this is the
tokeniser's view, not a pretty-printer's.

The two text-only siblings in the same family do **not** show it, which is
consistent with the normalisation being multimodal-server behaviour rather than a
property of the template lineage. That was checked, not assumed.

**The check.** Render a three-turn history and look at the assembled prompt, not
the response. If it contains `[{'type':` or `'text':` you have it. On vLLM,
`POST /tokenize` with `return_token_strs: true` is the cheapest route and shows
it unambiguously; `POST /v1/chat/completions/render` plus `POST /detokenize` also
works. Put the system message first in the probe, because a non-first system
message renders correctly and will mask the finding.

**The fix.** Client-side, because the template is the vendor's:

1. Send prior assistant and system content as **explicit single-element content
   part lists** rather than bare strings, so the normalisation is a no-op and the
   template's `content is string` test is not the deciding factor. Verify by
   rendering; do not assume it helps until you have seen the prompt.
2. If that does not clear it, strip prior turns to plain text and accept the loss
   of media in history, which at least gives the model a clean transcript.
3. Report it upstream. This is a template defect with a one-line fix in the
   template (handle the list case), and no client-side workaround is as good.

**If you miss it.** Every multi-turn number on this lane is measured on a
corrupted prompt, and the corruption grows linearly with conversation depth. It
will look like a depth-dependent capability property, and it is not.

**Negatives recorded.**

- Non-first system messages render correctly, so the bug is positional, not
  universal.
- The most recent turn is unaffected, so single-turn results are clean.
- The API response is normal in every respect; there is nothing to alert on.

**Related.**
[trap 04](04-history-reasoning-stripping.md) and
[trap 25](25-empty-think-blocks-poison-prefix-cache.md) are the neighbouring
history-corruption entries; this one differs in that the corruption is syntactic
noise rather than an absence, and in that it fires with no kwarg involved.

**Found.** 2026-07-27, first multimodal lane characterised in this line of work.
The session's own tooling review noted that the registry doctor could not have
found it, because the doctor had no render path on vLLM at the time. That gap is
now fixed.

**Attribution.** Blackwellboy.

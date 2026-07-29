# U11: the tool result renders empty, so the model calls the tool forever

**Reported by the Z.ai model team (@ZHANGYUXUAN-zR).**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** This is the strongest
provenance in this directory: the report is **from the model vendor**, pinned
on their own model repository, with the fix attached.

**Issue state: closed, fixed**: an updated `chat_template.jinja` shipped to
the model repository, with users confirming in-thread. No launch-command change
required.

**Primary source.** [zai-org/GLM-5.1 discussion #26, on the Hugging Face
model repository](https://huggingface.co/zai-org/GLM-5.1/discussions/26).
Read on 2026-07-28: the pinned post and the confirmation replies.

**Symptom.** An agent loop that never terminates. The model calls a tool, the
tool returns, the model calls the **same tool again** with the same arguments,
forever, until something caps it. It reads as a model failure, an inability to
use a result, and it is not. The model is being handed an empty tool message
and behaving correctly given what it can see.

**Mechanism, as stated upstream.** OpenAI's schema allows a message's `content`
to be a plain string or an array of content parts. The vendor's words:

> "vLLM and some other inference frameworks automatically convert tool message
> content from a plain string into an array of content parts"

The chat template shipped with the model handled **only** the string form.
Given an array, its render of the tool result produced **nothing**: not an
error, an empty string. The tool round trip completes, the prompt contains a
tool message with no content, and the model asks again.

The fix is a template replacement, not a serving change: "Replace your
`chat_template.jinja` with the updated version in our Hugging Face repository.
No changes to your launch command are required."

**Why this is worth an entry.** Three reasons, and the third is the one that
made it publishable rather than a link.

**The normalisation is invisible from both ends.** Your client sends a string.
The template sees an array. Neither side logs the conversion, and the request
and the response are both well formed.

**It is the same mechanism we measured ourselves, on a different message
role.** Trap
[67](../traps/template/67-history-rendered-as-object-repr.md) is a server
normalising message content into a list of content parts and the template
rendering the list, found here, on a multimodal server, on ordinary
conversation turns. This is that identical normalisation reaching the **tool**
role, found by a model vendor, on two serving stacks. An independent instance
of a mechanism we thought was ours is worth more than another instance of a
mechanism only we have seen. Trap
[68](../traps/template/68-multimodal-part-order-discarded.md) is a third face
of the same thing.

**The template is a versioned artifact that fixes serving bugs.** No weights
changed. A user who pulled the model a week earlier and pins their local copy
has the bug and will not find it by upgrading their server. That is trap
[03](../traps/reasoning/03-enable-thinking-default-drift.md)'s hazard,
template behaviour drifting between revisions of the same weights, with a
vendor advisory attached.

**What we have not done.** Nobody here has reproduced this. We hold no GLM
weights on any machine. We have not verified the before-and-after render, and
we have not checked whether other models in the family shipped the same
unfixed template, which is the more useful question now that this one is
fixed.

## If you have this stack

vLLM or SGLang, and any GLM-family checkpoint. The check needs no agent
framework and is faster as a render test than as a behaviour test.

1. Take the **old** template (repository history) and the **current** one.
2. Render an identical four-message history through both: user, assistant with
   a tool call, tool result, user. Supply the tool message's `content` as an
   **array of content parts**, which is what the server will have built.
3. Compare the two rendered prompts around the tool result.

**CONFIRM.** The old template renders the tool result as empty while the
current one renders its text, for the array form; and both render the string
form correctly. That last clause is what proves the array is the variable.

**REFUTE.** Both templates render the array form. Report the template revision
you tested, since the fix may have landed before the revision you have.

**The question actually worth answering** is not this model, which is fixed. It
is: **does the template you are serving handle the array form?** Every
model whose template predates OpenAI content-parts normalisation is a
candidate. Render a tool message with array content through the template of
each model you serve and check the output is non-empty. A table of models
checked, pass or fail, is the most useful thing anyone could add here.

## Attribution

Reported and fixed by the Z.ai model team, posted by @ZHANGYUXUAN-zR on the
GLM-5.1 repository. Credited in [HALL_OF_FAME](../HALL_OF_FAME.md).

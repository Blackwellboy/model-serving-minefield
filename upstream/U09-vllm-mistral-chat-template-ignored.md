# U09: the chat template you passed was ignored, and the warning scrolled past

**Reported by @jordan-taylor-aisi.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** By a vLLM maintainer
(@DarkLight1337) and by two Mistral employees (@patrickvonplaten,
@juliendenize) in the same thread.

**Issue state: closed, fixed**: closed 2025-10-09; @DarkLight1337 pointed at
[PR #26358](https://github.com/vllm-project/vllm/pull/26358), which
@juliendenize then describes as merged. The documentation that caused the
confusion was also corrected.

**Primary source.** [vllm-project/vllm#25401, "Chat template cannot be set for
mistral models"](https://github.com/vllm-project/vllm/issues/25401). Read on
2026-07-28: body and all ten comments.

**Symptom.** You pass `--chat-template`, the server starts, requests succeed,
and the template has no effect. Prompts are assembled by something other than
what you supplied. The message is
`'chat_template' cannot be overridden for mistral tokenizer` and it is logged
as a **warning**, in a startup log with hundreds of lines.

A second commenter, @sdtblckgov, described the consequence exactly: "vLLM's
output can be quite noisy, and we were running into bugs relating to this
because we didn't see this warning in the logs." They were debugging
downstream effects of a template that was never applied.

**Mechanism, as stated upstream.** Mistral checkpoints served through vLLM's
`MistralTokenizer` build prompts from `mistral-common` rather than from a Jinja
chat template, so **there is no template for `--chat-template` to override**.
The flag is accepted and dropped with a warning. @yyzxw read the code and
reached the same conclusion in the thread, adding that the documentation
appeared to be wrong.

The documentation was in fact wrong, and that is why the report happened at
all: vLLM ships Mistral-specific Jinja templates under `examples/`. The
reporter found them, used them, and reasonably concluded they should work.
@patrickvonplaten: "Mistral employee here! I think we should update the docs."

The supported route, from @juliendenize: if you need a custom template, use the
Transformers tokenizer path and remove `mistral-common`, noting that
Transformers now defaults to `mistral-common` when it is installed, and vLLM
installs it as a dependency. So the presence of a dependency silently selects
the prompt-assembly path.

**Why this is worth an entry.** Accepted-and-ignored is the registry's most
common silent-wrong shape and this is a strong instance of it: a **documented
flag**, with **shipped examples** that imply it works, ignored with a warning
in a log nobody reads. The reporter's use case makes the cost concrete, they
were generating transcripts with vLLM and collecting activations with
Transformers, and needed the tokenizations to match. A silently-ignored
template makes those two disagree in a way no error surfaces.

Its neighbours here are trap
[78](../traps/tools/78-tool-choice-accepted-and-ignored.md) and trap
[07](../traps/reasoning/07-reasoning-effort-silently-ignored.md), both
accepted-and-ignored; and trap
[56](../traps/template/56-checkpoint-ships-no-chat-template.md), which is the
same underlying fact, a checkpoint whose prompt assembly is Python rather than
a Jinja template, reached from the other direction and measured here.

**Even after the fix, the class is live.** "Which of several possible prompt
assemblers is this server actually using, and did my override reach it" is a
question no serving stack answers on the response. The check below asks it
empirically and is worth running on any stack.

**What we have not done.** Nobody here has reproduced this. We hold no Mistral
weights on any machine, which is a coverage gap already recorded in
the R2 dispositions *(private evidence archived)*.
We have not verified what PR #26358 changed, or whether the flag now raises
rather than warns.

## If you have this stack

vLLM and any Mistral checkpoint. Thirty minutes, and the method generalises to
any server and any model.

1. Write a chat template that is **unmistakable**: have it emit a nonsense
   sentinel such as `ZZTEMPLATEZZ` before every user turn. A subtle template
   cannot answer this question.
2. Serve the model with `--chat-template` pointed at it.
3. **Grep the startup log for `cannot be overridden`** before sending
   anything. Record whether the server warned, errored, or said nothing.
4. Ask the server what it actually built. If `/tokenize` is available, tokenize
   a two-message conversation with `return_token_strs` and look for the
   sentinel in the token strings, that is the prompt the model received, not a
   local library's guess. Failing that, prompt the model to repeat its input
   verbatim.
5. Control: serve a non-Mistral checkpoint with the same template and confirm
   the sentinel appears, so a negative result is about the tokenizer path and
   not about your template.

**CONFIRM.** The sentinel is absent from the assembled prompt while the server
returns 200 for every request, and the control run shows it present.

**REFUTE.** The sentinel appears, or the server refuses to start. **A refusal
to start is the fixed behaviour and is worth reporting**, with the version, so
this entry can record which release made it loud.

## Attribution

Reported by @jordan-taylor-aisi. The silent-warning consequence is
@sdtblckgov's. Code analysis by @yyzxw; maintainer confirmation by
@DarkLight1337; vendor guidance by @patrickvonplaten and @juliendenize.
Credited in [HALL_OF_FAME](../HALL_OF_FAME.md).

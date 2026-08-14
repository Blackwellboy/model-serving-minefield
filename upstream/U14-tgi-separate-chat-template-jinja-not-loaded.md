# U14: the checkpoint has a chat template, but the server looks in the old place

**Reported by @dhbrojas.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: none.** The public issue has user corroboration but no maintainer resolution in-thread.

**Issue state: open.** The issue remains open; the `huggingface/text-generation-inference` repository is now archived, so this is primarily a historical compatibility record.

**Primary source.** [huggingface/text-generation-inference issue #3247](https://github.com/huggingface/text-generation-inference/issues/3247), read on 2026-08-14. A second user in the thread reports manually editing tokenizer configuration to make chat completions runnable.

**Symptom.** The model/server can otherwise launch, but `/v1/chat/completions` fails with a template error saying the template was not found. Inspecting the checkpoint shows that a chat template exists, so the failure looks contradictory.

**Mechanism, as reported upstream.** Newer Transformers/checkpoint layouts can save the chat template as a separate `chat_template.jinja` artifact rather than embedding the template text in `tokenizer_config.json`. The affected TGI path expected the tokenizer-config location and did not load the separate file. The artifact is present; the runtime's loader contract does not look there.

**Why this is worth an entry.** "Does the checkpoint have a chat template?" is not a sufficient compatibility check. Template **location and loader behavior** are part of the serving contract. This is adjacent to [Trap 56](../traps/template/56-checkpoint-ships-no-chat-template.md), where the prompt constructor is Python rather than Jinja: in both cases a tool that checks one conventional location can report the wrong answer about how chat is actually constructed.

**What we have not done.** We have not run TGI on the affected checkpoint layout, and there is no maintainer-confirmed fix in the issue. The project is archived, so this entry does not predict that a future TGI release will resolve it.

## If you have this stack

Take a checkpoint revision whose template is stored as `chat_template.jinja` and not duplicated into `tokenizer_config.json`. Start the affected TGI version and test a plain generation endpoint plus `/v1/chat/completions`. Then make a local test copy in which the same template text is embedded where TGI expects it.

**CONFIRM.** The original copy loads but chat completion fails `template not found`, while the local copy with the identical template in the expected tokenizer-config location renders chat successfully.

**REFUTE.** The same affected TGI build loads the separate `chat_template.jinja` and chat completion succeeds without copying the template into tokenizer configuration. Record the exact TGI and Transformers revisions.

## Attribution

Reported by @dhbrojas in TGI issue #3247. User @bbkjunior independently reported the same class and a tokenizer-config workaround in the thread.

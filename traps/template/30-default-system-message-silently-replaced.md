# Trap 30: the template's default system message vanishes the moment you send your own

**Found by Blackwellboy.**

**Status: reproduced here** (structural, read directly from the shipped chat
template of the serving checkpoint; behavioral consequences are a separate
study, not this entry).

**Symptom.** Every experimental condition that supplies a system prompt
behaves differently from the no-system-prompt baseline, on every axis at
once, and the deltas refuse to decompose by what the system prompts say.
Or: a model is "fine bare" and "weird under any real prompt", and the
weirdness does not track prompt content.

**Symptom, second shape.** Two testers disagree about "no system prompt"
behavior because one sent no system message and the other sent an empty
one, and those are different conditions.

**Mechanism.** The chat template ships a built-in default system message
(for this model family, a trained identity paragraph). The template logic
uses it only when the caller supplies NO system message at all. Any caller
system message REPLACES the default wholesale; the default is not
prepended, merged, or preserved. Two structural consequences:

1. Every condition that supplies a system prompt evicts the model's
   default identity **by construction**. A comparison of "bare" versus
   "with system prompt X" is never only about X; it is also
   default-identity-present versus default-identity-absent, confounded
   with everything X says.
2. There is a silent opt-out arm: an **explicitly empty** system message
   (`{"role": "system", "content": ""}`) suppresses the default without
   adding anything, which means "no system message", "empty system
   message", and "any system message" are three distinct rendered prompts.
   Most harnesses treat the first two as identical.

**Stacks and builds bitten.** Read from the shipped
`chat_template.jinja` of a served checkpoint pair (a 3.25bpw EXL3-hybrid
community build and the NVFP4 upload of the same model, byte-identical
templates by md5). The construct is template-level and family-general:
any model whose template carries a default system message with
replace-not-merge logic has it. Whether it changes behavior is
model-specific and out of scope here.

**The check.** Do not infer this from behavior; read it:

1. Pull `chat_template.jinja` (or the `chat_template` field of
   `tokenizer_config.json`) from the exact checkpoint your server loads,
   not from the family's canonical repo.
2. `md5sum` the template and record it next to your results; compare
   against the build you published against before comparing numbers
   ([trap 03](../reasoning/03-enable-thinking-default-drift.md) is what
   happens when you do not).
3. Grep for the default system message and read the branch that guards
   it: does a caller system message replace it, merge with it, or leave
   it? Render all three arms (none, empty, real) through your serving
   path and diff the assembled prompts.

**The fix.** Decide explicitly, per experiment, which of the three arms
you are running, and say so next to every number. If you need the
default identity AND your own instructions, the template will not do it
for you: prepend the default text into your system message yourself, and
record that you did. If you need a true no-default baseline, an empty
system message is the opt-out, and it is a different baseline than
sending nothing.

**Found.** 2026-07-27, while designing the identity-prefix study; the
replace-not-merge branch was read from the serving template before any
cell ran.

**Attribution.** Blackwellboy. Related:
[trap 06](../reasoning/06-identity-sentence-eviction.md) (the behavioral
hypothesis that made this structure worth reading),
[trap 04](04-history-reasoning-stripping.md) and
[trap 25](25-empty-think-blocks-poison-prefix-cache.md) (other cases
where the render, not the request, is the fact).

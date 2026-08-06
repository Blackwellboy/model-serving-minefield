# Trap 70: the reasoning parser ships inside the checkpoint and is bundled with no serving stack

**Found by Blackwellboy.**

**Status: reproduced here on two checkpoints, with the without-parser arm
measured.**

**Symptom.** You serve a hybrid-reasoning checkpoint the normal way, with the
reasoning parser your stack ships for that family, or with none at all. Requests
succeed. Then you notice that thinking-off responses have empty `content`, or
that thinking-on responses have the reasoning text sitting in `content` behind a
close tag with no opener.

**Mechanism.** These checkpoints ship a **custom reasoning parser as a file in
the model repository**: `nano_v3_reasoning_parser.py` (18 lines) and
`super_v3_reasoning_parser.py` (1909 bytes). Neither is bundled with the serving
stack. You must fetch the file, mount it, and pass **both**
`--reasoning-parser-plugin <path>` and `--reasoning-parser <name>`.

Why the custom parser exists, in its own words: the DeepSeek-R1 parser it
subclasses puts **everything** into `reasoning` when it cannot parse a reasoning
block. That is correct for a model that always thinks. **These models have a
thinking-off mode**, so without the override, thinking-off responses land
entirely in the reasoning field and `content` is empty. The subclass exists
specifically to fix that.

And if you serve with **no** reasoning parser at all, `content` carries the
reasoning text, then a bare `</think>`, then the answer, with **no opening
`<think>`**, because the template pre-opens the block in the prompt and the model
only ever emits the closer. Client-side regexes that strip matched
`<think>...</think>` pairs find nothing to strip and the reasoning leaks into
user-visible output.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Nano 30B A3B NVFP4 on vLLM
0.25.1 (pip venv) and Nemotron 3 Super 120B A12B NVFP4 on vLLM 0.20.0 (vendor
container), both on single GB10-class nodes. Measured on Super with the parser
present: thinking-off returned `content` of 956 characters with `reasoning`
absent, which is the correct behaviour. The no-parser arm was captured on a
separate control server on both lanes.

**The check.** One request, one assertion:

```
send:   chat_template_kwargs {"enable_thinking": false}
assert: content is a non-empty string
```

If `content` is empty and `reasoning` is populated, your parser is wrong or
missing. Separately, grep any thinking-on `content` for a bare `</think>`; if you
find one with no opener, you have no reasoning parser at all.

Before downloading a checkpoint from this family, list its files and look for a
`*_reasoning_parser.py`. It is the cheapest possible check and it changes your
serve line.

**The fix.** Fetch the file at your pinned revision, mount it into the serving
process, and pass both flags:

```
--reasoning-parser-plugin <path>/<name>_reasoning_parser.py
--reasoning-parser <name>
```

Then read the parser source, because it is short and because **its kwargs are
part of your lane's kwarg surface** and appear in no card and no template. See
the [parser-only rescue kwarg draft](../reasoning/65-parser-only-rescue-kwarg.md) for a
worked example of a kwarg that exists only there.

**If you miss it.** Your thinking-off arm scores zero on everything, because
`content` is empty on every row, and it will look like a catastrophic capability
loss from disabling reasoning rather than a parsing configuration. Or your users
see the model's private reasoning, which is worse.

**Negatives recorded.**

- The plugin loaded without modification on both stacks and both parser files, so
  this is a packaging gap, not a compatibility problem.
- The parser is not gated and needs no token; it is a plain file in a public
  repository. The only obstacle is knowing it is there.

**Related.**
[trap 02](../template/02-orphaned-think-close-tag.md), the orphaned close tag
this produces when no parser is present;
[trap 38](../template/38-template-owns-the-opening-think-tag.md), the mechanism
that makes the close tag orphaned;
[trap 01](../reasoning/01-reasoning-field-two-names.md), which field the parser
writes to once it is correctly loaded.

**Found.** 2026-07-27 and 2026-07-28.

**Attribution.** Blackwellboy.

# U07: a well-formed tool call whose arguments contain the closing tag

**Reported by @ChefWu551.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** Root-caused in-thread by
@JustinTong0323, to the grammar rather than to the parser.

**Issue state: open** since 2026-06-05, with a fix PR from the reporter.

**Primary source.** [sgl-project/sglang#27336, "Qwen3.6 tool call with
tool_choice=\"required\" causes `</parameter` to appear in tool call
response"](https://github.com/sgl-project/sglang/issues/27336). Read on
2026-07-28: body and all three comments.

Corroborating, and read on the same date: a second report of malformed
arguments from the same parser on an NVFP4 build of the same family, posted
into [sgl-project/sglang#20069](https://github.com/sgl-project/sglang/issues/20069),
the Qwen3.5 tracking issue. That is a comment in a tracking list, not an issue
of its own, and it is cited here as a second sighting rather than as a source.

**Symptom.** Two failures from the same switch. Either the model repeats the
same tool call until `finish_reason="length"`, or, worse, you get a single
tool call that passes every structural check your client makes, with
`</parameter` fragments **inside the argument values**. The tool name is right,
the JSON parses, `finish_reason` is `tool_calls`. Then the executor runs a
lookup for a city called `Beijing</parameter` and fails somewhere with no
connection to the cause.

Setting `tool_choice="required"` is the trigger. Omit it and the same request
is clean. Switching `--tool-call-parser qwen3_coder` to `qwen` is also clean,
but the vendor's own deployment documentation recommends `qwen3_coder`, so the
configuration that produces this is the documented one.

**Mechanism, as stated upstream.** @JustinTong0323 placed it precisely, and
their first sentence is the one that matters: "**The root cause is in the
grammar used for `tool_choice=\"required\"`, not in the `qwen3_coder`
detector.**"

With `tool_choice="required"`, SGLang stops relying on the detector and routes
`qwen3_coder` through xgrammar's native structural tag,
`get_model_structural_tag(...)` into `Grammar.from_structural_tag`. The
constraint built for a string-typed parameter value is a `TagDispatch` whose
exclusion set does not stop the value from swallowing the closing
`</parameter>` tag. The span boundary is too wide, so the closing markup ends
up inside the value it was supposed to terminate.

A commenter put the operational consequence better than we would: this is
"worse than a parse failure because it produces a structured `tool_calls`
object that looks valid at the API level but contains contaminated arguments."

**Why this is worth an entry.** A loud parse failure costs you an hour. A
structurally valid call carrying corrupted arguments costs you a debugging
session in the wrong system entirely, and it can put bad values into whatever
the tool touches. Constrained decoding is exactly where this is most likely to
be believed, because the grammar is the thing you are trusting to make the
output well formed.

It also has a specific shape worth naming: **the failure is in the path taken
only when you constrain harder.** The default path is fine; asking for a
stronger guarantee routes you through different code. That is the same
structure as trap
[78](../traps/tools/78-tool-choice-accepted-and-ignored.md), where
`tool_choice` is accepted and ignored and fails open, different stack, same
field, opposite failure. Together they say: `tool_choice` is the least
trustworthy field in the tools API.

**What we have not done, and the one arm we did run.** Nobody here has
reproduced this, and this entry is the only one in the directory where we have
a partial negative of our own. It is worth stating precisely, because it
narrows the open question rather than answering it.

During our first-party SGLang bring-up, SGLang 0.5.16, Qwen3-4B bf16, GB10,
`tool_choice` absent, `auto` and `required` produced a clean, identical tool
call in all three arms, with arguments parsing as JSON and no markup
fragments. **That run used the `qwen` tool-call parser, and this report is
against `qwen3_coder`.** The pairing the report actually names is untested
here.

That is not a contradiction of the report. It is a match: the issue itself
states that `--tool-call-parser qwen` "also returns normally", and the
maintainer placed the fault in the grammar path taken for `qwen3_coder` under
`tool_choice="required"`. Our negative and the upstream positive agree on
where the boundary is, which is a mild independent check on the scoping and
nothing more.

We have not served any Qwen3.6-family checkpoint on SGLang, have not run the
`qwen3_coder` parser at all, and have not verified whether the reporter's PR
has landed. The results of that bring-up session are written and awaiting
publication.

## If you have this stack

SGLang and a Qwen3.6-family checkpoint. Under an hour, and the comparison is
what makes it decisive.

1. Serve with `--tool-call-parser qwen3_coder`, as the vendor docs recommend.
2. Define one tool with a **string** parameter, and prompt so a call is
   obvious.
3. Run 30 requests in each of two arms: `tool_choice` omitted, and
   `tool_choice="required"`. Everything else identical.
4. For each response, record `finish_reason`, whether the call repeated, and
   the **exact argument string**: do not read it through a client that
   pretty-prints, and do not eyeball it. Grep the raw value for `</`.
5. Control arm: repeat step 3 with `--tool-call-parser qwen`. We have run
   exactly this control on SGLang 0.5.16 and it was clean, so a contaminated
   result **here** would be the more surprising finding of the two and should
   be reported with the version.

**CONFIRM.** Argument values in the `required` arm contain `</parameter` or
other closing markup, or the call repeats to `finish_reason="length"`, at a
rate materially above the omitted arm, and the `qwen` parser arm is clean at
the same `tool_choice` setting. Report the counts per arm and your xgrammar
version, because the fault is in the grammar layer.

**REFUTE.** Both `tool_choice` arms produce clean arguments at
`qwen3_coder`. Report the SGLang and xgrammar versions; the reporter's PR
landing is the most likely explanation and the entry should then say
`closed, fixed`.

**Check the argument string, not the schema.** A validator that only asserts
the argument parses as JSON will pass every contaminated call in this report.
That is the whole trap.

## Attribution

Reported with a minimal reproduction and a fix PR by @ChefWu551. Root cause by
@JustinTong0323. The operational framing is @norika1207-lab's. The corroborating
NVFP4 sighting is @jhsmith409's. Credited in
[HALL_OF_FAME](../HALL_OF_FAME.md).

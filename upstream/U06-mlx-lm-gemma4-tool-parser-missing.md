# U06: native tool markup in content, and an empty tool_calls array beside it

**Reported by @EJellerson.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** Merged and closed by
@angeloskath.

**Issue state: closed, fixed**: parser merged 2026-04-04, issue closed
2026-04-08.

**Primary source.** [ml-explore/mlx-lm#1096, "Gemma 4 native tool calls are
not parsed, so the OpenAI-compatible tool_calls field stays
empty"](https://github.com/ml-explore/mlx-lm/issues/1096). Read on 2026-07-28:
body and all five comments.

**Symptom.** The model is calling the tool correctly and your client sees
nothing. `message.content` carries the model's native markup verbatim,

```
<|tool_call>call:get_current_time{timezone:<|"|>Asia/Tokyo<|"|>}<tool_call|>
```

and `tool_calls` is `[]`. There is no error and no warning. Every layer
looks healthy, so the natural conclusion is that the model cannot tool-call,
which is the opposite of what happened.

**Mechanism, as stated upstream.** `_infer_tool_parser()` in
`mlx_lm.tokenizer_utils` selects a tool parser by inspecting the chat
template. It had **no branch matching Gemma 4's delimiters**:
`<|tool_call>` / `<tool_call|>`, with `<|"|>` string escaping. Parser
inference failing does not raise; it means **the parse step never runs**, so
the raw text is returned as content.

The blast radius is two servers, not one: `mlx_vlm.server` relies on
`mlx-lm`'s parser inference at runtime before deciding whether to call
`process_tool_calls()`, so both are affected by the same missing branch.

Fixed by a `gemma4` tool parser with the delimiter and escaping handling plus
an auto-detection branch. @angeloskath: "Gemma 4 tool parser is merged now."

**Why we are publishing a fixed bug.** Two reasons.

**It names a version boundary on a stack we do cover.** mlx_lm has entries in
this registry and a [stack page](../stacks/mlx.md). If you are on a build from
before 2026-04-04, this is live, and the symptom does not look like a version
problem.

**The mechanism generalises past this fix, and that is the durable part.**
Parser selection here is *inferred from the chat template*, and inference
failure is silent by construction: no parser matched, so nothing parsed, so the
raw text passes through. Any model whose delimiters are newer than your
`mlx-lm` build lands in exactly this state, and the next new format will do it
again. That is why the check below is written against **the shape of the
output** rather than against Gemma 4.

This is the same class as trap
[19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md), where a missing
server flag turns structured tool calls into prose, and trap
[70](../traps/runtime/70-in-repo-parser-not-bundled.md), where the parser ships
inside the checkpoint and no serving stack bundles it. Different cause, same
observable, same wrong conclusion about the model.

**What we have not done.** Nobody here has reproduced this. Our Apple-silicon
coverage is one model on one machine and it is not Gemma 4; a previous session
declined to force-load Gemma 4 on that host because of a memory-thrash risk
recorded in the model index. We have not run either server against any Gemma 4
build, before or after the fix.

## If you have this stack

A Mac and `mlx_lm.server`. The general check is more useful than the specific
one and costs the same.

1. Serve any model with `mlx_lm.server` and send a request with `tools` that
   plainly requires a call.
2. Read **both** fields of the response, not just `tool_calls`.

**CONFIRM.** `tool_calls` is empty **and** `content` contains delimiter-shaped
markup, anything with angle brackets, pipes or a `call:` prefix that is
clearly not prose. That combination is parser-inference failure regardless of
which model produced it, and it is worth reporting for **any** model, not only
Gemma 4.

**REFUTE.** `tool_calls` is populated, or `content` carries ordinary prose
declining to call the tool. The second of these is a model behaviour and not
this trap; do not report it as one.

**The reusable version:** run it across every model you serve on that host and
report the pass or fail list with your `mlx-lm` version. A table of formats
that infer correctly is worth more than another instance of the Gemma 4 case,
which is closed.

## Attribution

Reported with the failing and expected payloads by @EJellerson. Fix by
@Blaizzy (PR #1093); an independent fix was also offered by @0xSoftBoi (PR
#1103). Merged and confirmed by @angeloskath. Credited in
[HALL_OF_FAME](../HALL_OF_FAME.md).

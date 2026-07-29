# U05: turning thinking off leaked tool calls into content, in one patch release

**Reported by @vfreysz.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** Diagnosed by @drifkin within
hours, with the mechanism named before a fix existed.

**Issue state: closed, fixed** in `v0.20.7-rc1`, confirmed by the reporter
against the release candidate. Introduced in `0.20.6`. The window is one patch
release wide.

**Primary source.** [ollama/ollama#15539, "[Bug] gemma4 parser fails to
extract tool_calls when combining system prompt + think:false +
tools"](https://github.com/ollama/ollama/issues/15539). Read on 2026-07-28:
body and all six comments, including the fix confirmation.

**Symptom.** Tool calling works, then stops, and only in one cell of the
matrix. With a system prompt **and** `think: false` **and** tools, the model
generates a correct tool call and it arrives as **raw JSON in `content`**,
with `tool_calls` empty. Drop the system prompt, or leave thinking on, and it
works. Because it is a three-way interaction, the natural minimal
reproduction, one of the three at a time, finds nothing.

**Mechanism, as stated upstream.** @drifkin, an Ollama maintainer, named it
from the report: with `think: false` the server had begun **passing an empty
think block to the model**, and that should have applied only to the larger
Gemma 4 models. The empty block changes what the parser is looking at, the
parser stops matching, and the model's output falls through to `content`
unparsed.

The reporter added the version boundary, which is the part that makes this
worth keeping: on `0.20.5` the same request worked "approximately 2 out of 4
times"; on `0.20.6` the failing cell became **consistent**. A regression that
turns an intermittent failure into a reliable one is easy to misread as a new
bug in something else.

**Why we are publishing a fixed bug.** Three reasons, and the tier records
fixed-in-version material only when they hold.

1. **It names a version window.** If you are pinned to `0.20.6`, and people
   pin, this is a live defect and the fix is an upgrade.
2. **The mechanism outlived the fix.** An injected empty think block changing
   what a downstream parser sees is not an Ollama-specific accident. It is the
   same mechanism as trap
   [25](../traps/template/25-empty-think-blocks-poison-prefix-cache.md), where
   empty historical think blocks move the prefix, and trap
   [26](../traps/tools/26-tool-call-inside-unclosed-think.md), where a tool
   call inside an unclosed think block is eaten by the parser. Three stacks,
   one shape.
3. **The thread contains a second finding that was never a bug and is not
   fixed.** After the fix, the reporter found that with `think: false` the
   small Gemma 4 model **stops calling tools at all** and asks clarifying
   questions instead. @drifkin: "Small models often do better tool calling
   with reasoning." The reporter recovered tool calls by making the system
   prompt more prescriptive. That is a real operating characteristic and it is
   still true.

**What we have not done.** Nobody here has reproduced this, neither the
parser regression nor the thinking-off tool-calling degradation. We have not
run Gemma 4 on Ollama at any version. The reporter's own before-and-after is
the entire evidence base, and it is one person on one machine.

## If you have this stack

Ollama and `gemma4:e4b`. The interesting run is the **degradation**, not the
regression, because the regression is fixed and the degradation is not.

**For the regression**, if you are pinned to `0.20.6`: send the full
two-by-two of system prompt on/off against `think` true/false, with tools, and
read where the tool call lands.

**CONFIRM.** Raw JSON in `content` with `tool_calls` empty in the
system-plus-`think:false` cell only, and clean `tool_calls` in the other three.

**REFUTE.** All four cells return structured `tool_calls`. Expected on
`v0.20.7` and later; report the version, because a refutation on `0.20.6`
would mean the trigger is narrower than the report states.

**For the degradation**, which is the open question and needs no old version:
hold everything fixed and vary only `think`, over 20 requests per arm on a
prompt that plainly requires a tool.

**CONFIRM.** The tool-call rate is materially lower with `think: false` than
with thinking on, and it recovers when the system prompt is made explicitly
prescriptive about calling tools without preamble.

**REFUTE.** Rates are comparable across the thinking arms. Report the model
size, because the claim is specifically about small models and a result on a
larger one does not settle it.

**Report counts, not impressions.** "It seemed worse" is the thing this
registry exists to replace.

## Attribution

Reported and version-scoped by @vfreysz, who also ran the fix confirmation and
found the thinking-off degradation. Diagnosed and fixed by @drifkin. Credited
in [HALL_OF_FAME](../HALL_OF_FAME.md).

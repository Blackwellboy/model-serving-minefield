# U02: repetition and presence penalties are accepted and discarded

**Reported by @BigBIueWhale.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer disputed.** The dispute is real and it is
recorded below, but read what it was about: a maintainer demonstrated that the
issue's **headline** claim was wrong. The penalty claim in this entry is a
different one of the three in the same report, and nobody addressed it.

**Issue state: open** since 2026-02-27. A fix for a sibling claim in the same
issue landed; this claim did not.

**Primary source.** [ollama/ollama#14493, "Qwen 3.5 27B: Tool calling
completely non-functional and repetition penalties silently
ignored"](https://github.com/ollama/ollama/issues/14493). Read on 2026-07-28:
the issue body and all fifteen comments, including the maintainer exchange.
The reporter's source-level write-up is linked from the issue and is
[here](https://github.com/BigBIueWhale/qwen3_5_27b_research/blob/master/qwen3.5_27b_inference_report.md).

**Symptom.** The model loops. You set `repeat_penalty`, or the model card's
recommended `presence_penalty`, and the loops are identical. The API accepts
the parameter, returns 200, and reports nothing. Every reasonable next step,
raise it further, try `frequency_penalty`, blame the quantization, blame the
model, is a dead end, because the value never reached a sampler.

**Mechanism, as stated upstream.** The reporter's claim is source-level and
specific: **Ollama's Go runner implements no penalty sampling at all**.
`repeat_penalty`, `presence_penalty` and `frequency_penalty` are accepted by
the API and silently discarded. The older C++ runner (`llamarunner`)
implements them correctly, but models routed through `OllamaEngineRequired()`
cannot use it. If that holds, the scope is **every model on the Go runner**,
not one family.

The reason it bites hardest on this family is that the model card explicitly
recommends a presence penalty to prevent repetition loops during thinking. The
documented mitigation for a documented failure mode is the thing being
dropped.

**The dispute, in full, because it matters.** The issue bundles three claims.
Maintainer @rick-github responded to the **title**: "tool calling completely
non-functional", by posting a session in which tool calling worked, and said:
"Your claim is that `Tool calling completely non-functional` which is
demonstrably incorrect. If you would like your bug report to be taken
seriously, being accurate would be a good start." That is a fair correction of
an overstated headline.

It is not a response to the penalty claim, and no comment in the thread is.
The tool-calling claim was separately taken seriously enough that
@rick-github linked [PR #14537](https://github.com/ollama/ollama/pull/14537),
and later commenters report tool calling working from v0.19.0. So the issue's
history is: headline overstated, sibling claim fixed, **penalty claim
unanswered and still open.**

**Do not read the thread's later comments as corroboration.** Two comments in
this issue and its sibling #14601 are near-identical posts from the same
account claiming production confirmation from an agent framework. They add no
conditions, no counts and no version, they appear verbatim-shaped in both
threads, and we are not counting them as independent reports. The evidence
here is the source-level analysis and nothing else.

**Why this is worth an entry.** Accepted-and-ignored is this registry's most
common silent-wrong shape and it has its own family: trap
[07](../traps/reasoning/07-reasoning-effort-silently-ignored.md), trap
[78](../traps/tools/78-tool-choice-accepted-and-ignored.md), trap
[85](../traps/reasoning/85-enable-thinking-typechecked-though-never-read.md),
and trap [77](../traps/reasoning/77-only-one-request-field-is-validated.md),
which is the Ollama one and which found that a lane accepted every invented
parameter it was sent. Trap 77's finding is about parameters the server does
not implement. This report is the stronger version of the same claim:
parameters the server **documents**, on a runner that does not read them.

**What we have not done.** Nobody here has reproduced this. We have not read
Ollama's Go runner source to check the claim, and we have not run the
loop-versus-penalty comparison. We have no measured evidence that the penalty
claim is true; what we have is that it is specific, falsifiable in twenty
minutes, and unanswered.

## If you have this stack

Ollama, any model that routes to the Go runner, and one prompt that loops
reliably at default settings.

1. Find a prompt that produces a visible repetition loop with default
   sampling. A long open-ended continuation at temperature 0 usually will.
2. Arm A: that prompt with `options: {"repeat_penalty": 1.0}`.
   Arm B: identical, with `options: {"repeat_penalty": 1.8}`.
   Hold the seed and every other option fixed. Use `/api/chat` so the option
   name is unambiguous.
3. Run 20 completions per arm and count repeated n-grams, 4-grams occurring
   more than twice is a serviceable measure.
4. Repeat with `presence_penalty` and `frequency_penalty`.
5. **The control that makes this decisive:** run the same pair against a model
   that Ollama routes to the C++ runner. If penalties bite there and not on the
   Go runner, the mechanism is the runner split rather than the parameter name.

**CONFIRM.** The two arms are statistically indistinguishable on the Go
runner, ideally byte-identical at a fixed seed, which is a stronger signal
than a rate, while the same contrast moves the C++ runner.

**REFUTE.** The high-penalty arm reduces repetition on the Go runner. Report
the Ollama version, because a fix landing is the most likely reason you would
see this.

## Attribution

Reported with source-level analysis by @BigBIueWhale. Headline correction and
the tool-calling fix pointer by @rick-github. Credited in
[HALL_OF_FAME](../HALL_OF_FAME.md).

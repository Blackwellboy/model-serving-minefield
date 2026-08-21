# U17: client stop strings can fire inside reasoning and erase the answer

**Reported by @Capicua25x.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The fix was reviewed and merged by the recipe maintainer.

**Issue state: closed, fixed.** PR #21 is merged on the source repository's current main.

**Primary source.** [tonyd2wild DeepSeek-V4-Flash PR #21](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/pull/21), read on 2026-08-21.

**Symptom.** A reasoning model returns HTTP 200 with `content: null`, or an evaluation score collapses, only when the client supplies stop strings. The raw generation was cut while the model was still reasoning, so `</think>` never appeared and the reasoning parser had no completed answer segment to expose.

The contributor measured this on 2x DGX Spark / GB10, TP=2, k=5, serving DeepSeek-V4-Flash-0731. A seed reproducer changed from 43 generated tokens plus null content to 344 tokens plus a correct answer after the serving fix. On GSM8K n=50 at temperature 0.6 / top_p 0.95, the reported null count moved from 8-15 to 1 and score from 0.66-0.84 to 0.98. The remaining null was explicitly attributed to a separate runaway-reasoning mechanism.

**Mechanism.** The affected vLLM v1 detokenizer evaluates client stop strings over the whole generated stream. With a think-in-prompt template, generation starts inside the reasoning segment. If chain-of-thought naturally repeats a stop phrase such as `Question:`, the detokenizer stops before `</think>` and the parser reports no content.

Speculative decoding adds a second edge: one detokenizer update may contain multiple accepted tokens, including the tail of reasoning, `</think>`, and answer content. The reviewed fix therefore advances the stop-check offset past the reasoning-end marker before re-enabling stop matching; merely toggling a boolean when the marker is seen can still let a stop in the same multi-token chunk fire retroactively inside reasoning.

**What we have not done.** We have not reproduced this on Blackwellboy infrastructure or established which newer vLLM builds still carry the behavior. The source patch is keyed to the reported build and should not be force-applied across moved code.

## If you have this stack

Pin the affected build and a think-in-prompt model. Use a prompt whose reasoning predictably contains one client stop string. Run the same request with the stop string present and absent, capturing raw output, parser fields, finish reason and generated-token count. Then repeat with a guard that keeps client stops dormant until the reasoning-end marker; keep a non-thinking control where the same stop must still work normally.

**CONFIRM.** The unguarded thinking request stops before the reasoning-end marker and loses/empties final content, while the guarded request completes reasoning and returns the answer; the non-thinking control still honors the stop.

**REFUTE.** On the pinned allegedly affected build, the same stop string is already scoped to post-reasoning content, or enabling the guard makes no difference because the raw stream was never cut inside reasoning.

## Attribution

Reported and measured by @Capicua25x in PR #21; the source repository maintainer reviewed and merged the fix. The registry has not independently reproduced the measurement.

# Trap 16: finish_reason=length is not a failure signal, and stop is not a success signal

**Found by @apollo-mg and Blackwellboy.**

**Status: reported by others and reproduced here** from the opposite direction; the two datasets together give the full rule.

**Symptom.** A benchmark buckets every cap-hit as a failure, or every clean
stop as an answer, and the aggregate moves by whole points for reasons that
have nothing to do with the model's ability.

**Mechanism.** `finish_reason` tells you how generation ended, not whether
you got usable output. Both directions fail:

- **Cap-hit but PASS.** @apollo-mg's HumanEval+ run: problem 47 hit the 16K
  ceiling twice and **passed both times**, complete correct code followed by
  extra generation to the cap. His own config doc had said cap-hits must be
  bucketed as failures; he corrected it in public, with the mistake left
  visible: "finish_reason=length isn't a failure signal on its own"
  ([the correction](https://github.com/TheTom/offlabel/pull/10#issuecomment-5084128736)).
- **Clean stop but no answer.** Our temperature-controlled replication on
  the same benchmark: of 22 no-extractable-code rows in the thinking-ON
  arm, **8 finished with `stop`**, not `length`. Conversely 14 of 15 actual
  cap-hits contained zero extractable code with heavily compressed
  degeneration tails
  ([pr10-replication](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/pr10-replication)).

Same field, opposite lies, on the same benchmark, two stacks.

**Stacks and builds bitten.** llama.cpp fork on quad P100 (Q2_K_XL build,
@apollo-mg) and vLLM on GB10 (NVFP4, ours). The signature also differs by
model: on one model budget converts cap-hits into passes (trap 12), on
another they are degeneration loops budget cannot fix. You have to look.

**The check.** Bucket on **extractable output first** (did you get code
that parses, an answer that scores), then split each bucket by
finish_reason to diagnose truncation versus loop versus verbosity. Never
map finish_reason directly to pass/fail.

**The fix.** Score content, use finish_reason only as a diagnostic
dimension, and when cap-hits appear, re-run the solvable subset at a larger
budget before publishing (the discriminating experiment @apollo-mg then
specified: only truncations on otherwise-solvable problems separate
"needs budget" from "degenerates").

## Added 2026-08-17: `length` does not identify which length budget ended the request

A separate public Qwen3.8 serving report from TheTom/Offlabel sharpens the
same rule from the context-accounting side: a request can return
`finish_reason=length` because the **total server context window** is
exhausted even when the requested output cap itself still has substantial
room. That observation is **public-source evidence, not reproduced here** at
the time of this addendum.

The practical check is stronger than inspecting `max_tokens`: record prompt
/input tokens, configured server context, requested output budget, completion
tokens and remaining headroom together. If accumulated conversation history
consumes the window, `length` still cannot tell you whether the relevant
boundary was the output cap or total context.

This is an extension of Trap 16, not a new trap. It does not change the
content-first scoring rule above. Source/reconciliation context:
[issue #40](https://github.com/Blackwellboy/model-serving-minefield/issues/40).

**Found.** 2026-07-26, in public thread; our complementary data same week.

**Attribution.** @apollo-mg (the correction, credited with respect for
making it in public); Blackwellboy (the stop-but-empty complement). The
2026-08-17 total-context addendum is credited to TheTom/Offlabel as a public
source observation pending first-party reproduction.

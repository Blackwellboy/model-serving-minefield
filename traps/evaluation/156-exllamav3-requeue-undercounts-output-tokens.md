# Trap 156: repeated ExLlamaV3 requeues can under-report completion tokens and derived tok/s

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #171](https://github.com/Blackwellboy/model-serving-minefield/issues/171)); source inspection pins the counter carry-forward expression.

**Symptom.** Long replies show implausibly low `usage.completion_tokens` and server-reported tok/s, sometimes with `finish_reason=length` even though the reported count is far below `max_tokens`. Generation text itself is fine.

**Mechanism.** ExLlamaV3 requeues long jobs. The inspected code carries `rq_new_tokens` forward as the current segment's `new_tokens` instead of adding it to the already-carried value, so after multiple requeues earlier segments disappear from the final count. TabbyAPI uses that final count for OpenAI usage and its logged generation rate.

**Stacks and builds bitten.** vcruz305/exllamav3 `047ce72...`, TabbyAPI `be74bf0`, long Qwen3.8-Flash-Next-family replies on DGX Spark. The same carry expression was also visible in upstream history.

**The check.** Retokenize returned reasoning+content with the served tokenizer and compare against reported completion tokens. A length stop with a reported count far below the explicit cap is a strong signature.

**The fix.** Until the counter is fixed and validated, derive output length from returned text for long/requeued jobs. The obvious cumulative carry-forward patch is source-suggested but was not claimed as tested here.

**Found.** 2026-09/10, long TabbyAPI qualification.

**Attribution.** @scottleimroth.

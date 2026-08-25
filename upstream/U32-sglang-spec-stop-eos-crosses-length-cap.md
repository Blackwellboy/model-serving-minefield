# U32: a speculative accept run can leak tokens after EOS when it also crosses the length cap

**Reported by @842974287.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The fix was reviewed and merged into SGLang.

**Issue state: closed, fixed.** SGLang PR #33758 is merged.

**Primary source.** [SGLang PR #33758](https://github.com/sgl-project/sglang/pull/33758), read on 2026-08-25.

**Symptom.** One speculative multi-token commit can contain an EOS/stop and cross `max_new_tokens` in the same step, producing emitted output shaped like `[..., <eos>, <junk>]` instead of trimming at the stop.

**Mechanism.** Finish-state handling checked the length cap before stop strings and stop tokens. A multi-token speculative accept therefore could be classified as a length finish before the in-budget stop was processed, preserving over-accepted tokens after the stop. The merged fix gives in-budget stop/EOS precedence and caps stops that occur beyond the budget.

**What we have not done.** We have not reproduced the affected SGLang speculative finish-state path on Blackwellboy infrastructure.

## If you have this stack

Pin the pre-fix build and construct a speculative step whose accepted run contains EOS or a stop string before the length cap plus at least one accepted token after it. Compare emitted ids and finish reason with the fixed build and a non-speculative control.

**CONFIRM.** The pre-fix request emits a token after an in-budget stop/EOS or reports length where the fixed build trims at the stop.

**REFUTE.** The pinned pre-fix path already trims at the in-budget stop and never emits accepted tokens after it.

## Attribution

Reported and fixed upstream by @842974287 in SGLang PR #33758. The registry has not independently reproduced the measurement.
# Trap 146: a correct context rejection can become an indefinite downstream retry loop

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported** ([issue #147](https://github.com/Blackwellboy/model-serving-minefield/issues/147)).

**Symptom.** A request appears to hang for hours behind a gateway even though the model server is healthy. The gateway repeatedly tries context compression and retry logic.

**Mechanism.** The model server correctly rejects a request that exceeds its configured context cap. A downstream gateway interprets the clean context error as recoverable, attempts compression, fails to compress enough, backs off, and retries instead of surfacing the launch/config mismatch. The original server error is therefore converted into a silent operational stall.

**Stacks and builds bitten.** vLLM serving an approximately 27B NVFP4 model behind a LiteLLM-compatible gateway with automatic context-compression retry.

**The check.** Compare the server's actual configured context limit with the gateway/client assumption. Preserve the first upstream error before retry logic. A context-exceeded response must be distinguishable from a transient transport failure.

**The fix.** Align the server launch-time context with the intended deployment contract, and bound/terminate gateway compression retries when the upstream limit is authoritative.

**Found.** 2026-09, production gateway stall.

**Attribution.** @scottleimroth.

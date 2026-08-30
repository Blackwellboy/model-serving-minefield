# U40: XGrammar can keep advancing through a speculative token batch after the matcher has terminated

**Reported by @datanerdie.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** vLLM merged PR #52805 with targeted unit/live coverage for the reported XGrammar speculative-batch termination defect.

**Issue state: closed, fixed.** vLLM issue #52767 is closed and fix PR #52805 is merged as `12f64b39d29282437e35be9aa5db432fb2a1a6e6`.

**Primary source.** [vLLM issue #52767](https://github.com/vllm-project/vllm/issues/52767) and merged [PR #52805](https://github.com/vllm-project/vllm/pull/52805), read on 2026-08-30.

**Symptom.** With MTP speculative decoding and a structured-output/tool path that actually builds a structural tag, XGrammar can receive another drafted token after it has already accepted a terminating stop token. The original report saw matcher warnings only when speculation was enabled; the corresponding non-speculative arms were clean. The reporter scoped the measured impact carefully: tool calls stayed correct in the tested payloads, so the initial symptom was wasted matcher work/log noise rather than proven wrong user output.

**Mechanism.** `accept_tokens()` processed a list of speculative tokens but only synchronized the cached `_is_terminated` state after the loop. If a stop/EOS terminated the matcher before the end of that list, later drafted tokens in the same batch could still be fed into an already-terminated FSM. The merged fix updates termination state after each accepted token and stops the batch immediately; `validate_tokens()` similarly stops validation at termination, and `reset()` clears the cached termination flag.

PR #52805's live test deliberately aligned EOS with an early MTP draft slot so trailing draft tokens remained after EOS. Before the fix the matcher advanced after termination; after the fix the PR reports 20/20 requests without matcher errors, plus a strict-JSON second-advance case moving from HTTP 500 to 5/5 HTTP 200.

**What we have not done.** We have not reproduced this XGrammar/MTP path on Blackwellboy infrastructure. The upstream fix is XGrammar-specific and should not be generalized to every structured-output backend without separate evidence.

## If you have this stack

Pin a pre-fix vLLM build, enable MTP/speculative decoding, and construct a structured-output request whose accepted speculative run contains a terminating stop/EOS before the final draft position. Capture matcher logs and the exact accepted token IDs. Repeat with PR #52805's merged commit or a descendant, holding model, grammar and speculative depth fixed.

**CONFIRM.** The pre-fix build feeds at least one token after matcher termination or produces the corresponding matcher warning/error, while the fixed build stops the speculative batch at the terminating token and leaves the matcher state synchronized.

**REFUTE.** The pinned pre-fix build already stops the batch exactly at matcher termination, or the same post-termination advance persists with the merged fix proven active.

## Attribution

Reported by @datanerdie in vLLM issue #52767; fixed by @sfeng33 in merged PR #52805. The registry has not independently reproduced the measurement.

# Trap 23: the streamed answer lands in the reasoning channel, content stays empty

**Found by @xy3xy3 (vLLM issue), independently confirmed in-thread by @ArtemVorozhtsov.**

**Status: reported by others** (upstream vLLM bug report with reproduction,
closed as fixed by [PR #40820](https://github.com/vllm-project/vllm/pull/40820));
not independently reproduced here.

**Symptom.** Streaming clients show blank replies from a model that is
working. Every SSE chunk carries text under `delta.reasoning` while
`delta.content` stays empty for the whole stream, even with thinking
explicitly disabled. The same request with `stream: false` returns a
correct, populated `content`. An agent loop or UI that concatenates only
`content` deltas measures a silent, broken model that is actually
answering on every request.

**Mechanism.** The server-side reasoning parser routes streamed tokens
into the reasoning channel regardless of the thinking kwarg; the
stream-mode and non-stream-mode code paths classify the same output
differently. `enable_thinking: false` does not force the final answer
into `content` on affected builds.

**Stacks and builds bitten.** Qwen 3.6 family (confirmed in-thread on
Qwen3.6-35B-A3B) on vLLM v0.20.0 with `--reasoning-parser qwen3` and
`enable_thinking: false`
([vllm #40816](https://github.com/vllm-project/vllm/issues/40816), closed
as fixed by
[PR #40820](https://github.com/vllm-project/vllm/pull/40820)). The failure
is build-scoped: whether your lane has it depends on your engine version,
which is exactly why the check below belongs in preflight rather than in
memory.

**The check.** One streamed request against your lane, thinking off,
logging the key set of every delta: does the answer text arrive under
`content`, `reasoning`, or `reasoning_content`? Then the same request
with `stream: false`. Confirmed if the streamed answer exists only in
reasoning deltas while the non-streamed answer sits in `content`. Assert
streaming and non-streaming parity before trusting any streamed harness
number.

**The fix.** Upgrade past the engine fix for your stack (vLLM: PR #40820).
Until then, clients must read the reasoning delta fields as a fallback
answer channel, which is ugly and mixes channels, so prefer the upgrade.
Never score a model through a streaming path whose delta placement you
have not probed.

**Found.** 2026-07-27 (mined from upstream; issue filed 2026-04).

**Attribution.** @xy3xy3 (vLLM issue with API shape), @ArtemVorozhtsov
(independent in-thread confirmation with exact flags), vLLM maintainers
(fix). Related entries:
[trap 01](01-reasoning-field-two-names.md) (read side, two field names),
[trap 20](20-reasoning-write-field-name-diverges.md) (write side),
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md) (a different
cause of empty content with HTTP 200).

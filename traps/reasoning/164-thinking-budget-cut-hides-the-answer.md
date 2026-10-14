# Trap 164: a thinking-token budget that actually cuts the reasoning hides the answer and runs to max_tokens

**Found by Blackwellboy.**

**Status: reproduced here** (runnable check below against the affected lane;
counts measured here on 2026-10-15, raw not published).

**Symptom.** You add a per-request reasoning cap, for example
`"thinking_token_budget": 64`, to stop a reasoning model thinking for too long.
The server accepts it. Requests whose reasoning stays under the cap behave
normally. Requests whose reasoning reaches the cap come back with
`content` empty, `finish_reason: "length"` and `completion_tokens` equal to
your `max_tokens`, after a much longer wait than an uncapped request. The
reasoning field holds a sentence cut off mid-thought, and
`completion_tokens_details.reasoning_tokens` equals the cap exactly. The cap
did not shorten the request; it removed the answer and made it slower.

Measured on one lane, the same short arithmetic question
(`max_tokens: 600`, temperature 1.0, top_p 0.95, non-streaming, 3 runs each):

| `thinking_token_budget` | Answer delivered | `completion_tokens` | `reasoning_tokens` | `finish_reason` | Time |
|---|---|---|---|---|---|
| not sent | **3/3** | 80-129 | 75-124 | `stop` | 2.2-3.1 s |
| 32 | **0/3** | 600 | 32 | `length` | 35-37 s |
| 64 | **0/3** | 600 | 64 | `length` | 35 s |

A harder question with `max_tokens: 3000` and budgets of 256, 512 and 1,024
gave the same shape on every run: `reasoning_tokens` equal to the budget,
empty `content`, `length`, all 3,000 tokens spent, in 147-178 s where the
uncapped request spent the same 3,000 tokens in 64 s. With streaming, the
deltas stop after the cut: the capped run emitted 12 reasoning deltas and **no
content delta at all** before finishing at 600 tokens, so the ~568 tokens after
the cut appear in neither channel. A run whose reasoning finishes under the cap
(125 of 128) answers normally, which is why a quick test with a generous cap
looks fine.

**Mechanism.** Not established here. What the measurements pin down: the cap
is enforced (reasoning stops at exactly the budget, mid-sentence), generation
then continues until `max_tokens`, and none of the continuation is surfaced as
`content` or as reasoning, in streamed or non-streamed responses. Decode after
the cut ran at about 17 tokens/s (600 tokens in 35 s; 3,000 in 147-178 s),
against about 47 for the uncapped 3,000-token request on the same lane.
A plausible reading, not verified, is that the forced end-of-thinking token the
budget path inserts is not the marker this model's reasoning parser splits on,
so everything after it is held back as unparsed output. Confirming that needs
the raw token stream after the cut.

How this differs from its neighbours:
[trap 153](153-thinking-budget-hardcodes-wrong-marker-ids.md) is the opposite
failure, a budget that silently never fires.
[Trap 12](../evaluation/12-empty-content-at-token-ceiling.md) empties `content`
because the reasoning itself used the whole `max_tokens`; here the reasoning
is short and the rest of the budget disappears.
[Trap 162](162-thinking-on-short-answer-never-closes-think-block.md) files the
answer as reasoning with `finish_reason: "stop"`; here there is no answer
anywhere and the finish is `length`.

**Stacks and builds bitten.** DeepSeek-V4.1-Flash EXL3 2.9 bpw (a local graft
of the public 2.9 bpw pack) served by an EXL3 build of vLLM with
`--tokenizer-mode deepseek_v41 --reasoning-parser deepseek_v41
--tool-call-parser deepseek_v41`, DSpark speculative decoding (k=3), tensor
parallel 2 on two DGX Spark (GB10) nodes, chat completions with the field
`thinking_token_budget` in the request body. `reasoning_effort` was `xhigh`
(budget 75 on this build); the no-budget control used the same request. Not
tested: other models, other reasoning parsers, stock vLLM builds, or the
`max_tokens`-relative variants of a thinking cap.

**The check.** Send one request whose reasoning will exceed the cap and one
control, with a small `max_tokens` so the failure is cheap:

```bash
B='{"model":"YOUR-MODEL","max_tokens":300,"messages":[{"role":"user","content":"A train leaves at 09:47, travels 2 h 38 min and also waits 17 min that is not in the trip time. Arrival time? Think it through, then reply as HH:MM."}]'
curl -s "$BASE/chat/completions" -H 'Content-Type: application/json' -d "$B}"                               | jq '{c:.choices[0].message.content, f:.choices[0].finish_reason, u:.usage}'
curl -s "$BASE/chat/completions" -H 'Content-Type: application/json' -d "$B,\"thinking_token_budget\":32}" | jq '{c:.choices[0].message.content, f:.choices[0].finish_reason, u:.usage}'
```

You are bitten if the capped request returns empty `content`,
`finish_reason: "length"`, `completion_tokens` equal to `max_tokens` and
`reasoning_tokens` equal to the budget, while the control answers. Run it more
than once: a request whose reasoning happens to finish under the cap passes.

**The fix.** Do not use a thinking-token budget on this stack until the check
passes. To make a reasoning model faster without it, lower the effort level
or switch thinking off for the calls that do not need it (for example, tool-loop
continuations in an agent), and verify the answer is present in `content` on
every request rather than trusting the 200.

**Found.** 2026-10-15, tuning reasoning settings for an agent harness.

**Attribution.** Blackwellboy.

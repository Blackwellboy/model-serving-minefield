# Trap 165: turning thinking off to make an agent fast passes the quick checks and fails the reasoning

**Found by Blackwellboy.**

**Status: measured here, raw not published** (21-task suite x3 and two
replayed stretches of a real agent session, 2026-10-15; the check below
re-derives the shape on your own lane).

**Symptom.** Your agent is slow on a reasoning model: every step waits while
the model thinks. You switch thinking off. The agent is suddenly fast, and
everything you try looks fine: it reads files, runs commands, follows tool
output and plans the next step. Days later it gets a sum, a date difference or
a piece of code tracing wrong, inside a turn where it looked confident. Nothing
errored; the answer was just worse.

Measured on one lane inside a real agent harness (36 tools, about 29k tokens of
system prompt), 21 tasks x 3 runs, 60 gradeable calls per arm:

| | in-agent reasoning | tool follow-ups | planning | final answers | total | mean per call |
|---|---|---|---|---|---|---|
| thinking off | **8/24** | 14/15 | 12/12 | 9/9 | 43/60 | 1.7 s |
| thinking on, `low` | 24/24 | 15/15 | 12/12 | 9/9 | 60/60 | 3.3 s |
| thinking on, `max` | 24/24 | 15/15 | 12/12 | 9/9 | 60/60 | 6.4 s |

Thinking off loses almost nothing on the calls a quick check exercises (tool
follow-ups, planning, final answers) and two thirds of the in-agent reasoning
tasks (arithmetic, code tracing, time maths). That is why the switch looks
free.

The opposite default is the reason the agent was slow. Replaying 11 real steps
from a slow session (browser automation, warm cache, the same requests each
time):

| policy | time |
|---|---|
| thinking off on every call | 70 s |
| thinking on (`low`) on every call | **258 s** |
| think on the first call after a user message, off on tool-loop continuations | **53 s** |

**Mechanism.** Most model calls in an agent loop are continuations: the last
message is a tool result and the job is to read it and pick the next tool.
Thinking adds little there. The calls where thinking changes the answer are
the ones right after the user speaks, where the model works out what to do or
answers. A single per-lane setting cannot tell the two apart, so it is either
slow on every continuation or weak on every answer. The scheduled policy came
in under thinking off on this one stretch; the reason was not investigated,
so read it as "about thinking-off speed", not as faster.

How this differs from its neighbours:
[trap 29](29-server-reasoning-off-is-not-an-off-switch.md) is a server
default that does not turn thinking off; here it is really off and that is
the problem.
[Trap 158](158-empty-thought-markers-count-as-reasoning.md) is a reporting
artifact after tools with thinking off; nothing here is mis-reported.
[Trap 164](164-thinking-budget-cut-hides-the-answer.md) is why a thinking-token
budget is not the middle ground on the same lane.
[Trap 166](166-per-call-thinking-switch-splits-prefix-cache.md) is the cache
cost of switching per call, which the replay above already includes.

**Stacks and builds bitten.** DeepSeek-V4.1-Flash EXL3 2.9 bpw served by an
EXL3 build of vLLM with the `deepseek_v41` tokenizer and parsers, DSpark
speculative decoding (k=3), tensor parallel 2 on two DGX Spark (GB10) nodes,
thinking switched off with `reasoning_effort: "none"` plus
`chat_template_kwargs: {"enable_thinking": false}` (a real boolean), on with
`reasoning_effort: "low"`. Not tested: other models. A model whose reasoning
does not depend on thinking would show no gap, which the check tells you.

**The check.** Run the same short reasoning questions inside your agent's
real system prompt and tool list, thinking off and on, at least three times
each, and grade the final number, not the prose. With a plain endpoint the
smallest version is:

```bash
Q='A meeting starts at 10:50 and runs 2 h 25 min, then a 35 min break. When does the break end? Reply HH:MM only.'
for t in false true; do for i in 1 2 3; do
  jq -n --rawfile sys your_agent_system_prompt.txt --arg q "$Q" --arg m "$MODEL" --argjson t "$t" \
    '{model:$m, max_tokens:2000, messages:[{role:"system",content:$sys},{role:"user",content:$q}], chat_template_kwargs:{enable_thinking:$t}}' \
  | curl -s "$BASE/chat/completions" -H 'Content-Type: application/json' -d @- \
  | jq -r --arg t "$t" '"thinking=\($t) " + (.choices[0].message.content // "")'
done; done
# expected answer: 13:50
```

Use the switch your stack actually honours (see
[trap 07](07-reasoning-effort-silently-ignored.md) and
[trap 58](58-reasoning-effort-injects-hidden-preamble.md)). You are bitten if
thinking off gets questions like this wrong that thinking on gets right, while
your tool-step checks pass in both.

**The fix.** Do not choose one thinking setting for the whole agent. Think on
the first model call after each user message and switch thinking off when the
last message is a tool result (a request middleware or a small proxy in front
of the server can do this per call). Measure it on your own session replay
before trusting the speed numbers above, and keep a way to force thinking on
for a hard session.

**Found.** 2026-10-15, tuning a slow DeepSeek-V4.1 lane for an agent harness.

**Attribution.** Blackwellboy.

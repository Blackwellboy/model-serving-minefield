# Trap 173: a valid tool call is not proof of the correct tool choice

**Found by Blackwellboy.**

**Status: measured here, raw not published.** Controlled before-and-after
measurements on a first-party agent stack; the raw sessions are not published.
The check below needs only your own prompts and tool log.

**Symptom.** An agent makes a syntactically valid tool call, the parser
accepts it, the tool runs successfully, and the next answer still derails
badly. Every layer reports success, so the trace looks healthy even though the
tool the model picked had nothing to do with the user's task.

**Mechanism.** Tool correctness has at least two layers: structural validity
and semantic relevance. A model can emit a perfectly parseable call to the
wrong tool. If that tool returns a large payload, the irrelevant result is
injected into context and amplifies the original routing mistake on the next
turn. Parser success and execution success say nothing about whether the
right tool was chosen.

**Stacks and builds bitten.** A first-party autonomous-agent stack using a
locally served OpenAI-compatible model (a Qwen3.8 family checkpoint) with
explicit tool calling and a skill-loading tool, 2026-09-12. The serving parser
was tested separately and ruled out: the raw completion already contained the
wrong tool request. A targeted routing guard took executed wrong-tool calls to
0 of 30 on unrelated control prompts while the legitimate route stayed 20 of
20.

**The check.** Run a set of unrelated control prompts and a set of legitimate
prompts for the tool in question. For each, record separately: the tool the
model requested in the raw completion, the parsed tool, the executed tool,
whether it was relevant to the task, the result size, and the next answer.
Confirmed when the model repeatedly requests the unrelated tool while the
parsed and executed calls faithfully match what it requested. Refuted when the
wrong call cannot be reproduced under matched prompts, or appears only after
parsing or execution.

**The fix.** Add a narrow routing guard at the agent boundary for high-impact
tools: block only semantically invalid routes, keep legitimate routes working,
and fail closed for the targeted action. Do not disable the tool globally, and
do not file a semantic routing error as a parser bug.

**Found.** 2026-09-12, separating model tool selection from parser behaviour
in a local autonomous-agent stack.

**Attribution.** Blackwellboy.

**Related.** [78](78-tool-choice-accepted-and-ignored.md),
[42](../evaluation/42-single-turn-harness-scores-tool-calls-as-wrong.md).

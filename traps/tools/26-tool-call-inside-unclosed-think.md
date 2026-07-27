# Trap 26: the tool call is emitted inside an unclosed think block, and the parser eats it

**Found by @kik4444 (llama.cpp issue) and tfriedel (mechanism writeup).**

**Status: reported by others** (open llama.cpp bug with 57 comments, a
merged vLLM parser fix, and a third-party lab writeup that traces the
full mechanism); not independently reproduced here.

**Symptom.** An agent turn ends with stop reason `stop` instead of
`toolUse`. The structured `tool_calls` array is empty, but the raw model
output contains a complete, well-formed `<tool_call>...</tool_call>`
block, parked inside the thinking field. The model did the work; the
agent concludes the task is done, or that the model "cannot tool-call",
and dies or loops.

**Mechanism.** Qwen 3.5 and 3.6 sometimes skip the closing `</think>` and
jump straight into a tool call. The reasoning parser then treats the
entire remainder of the output as reasoning, so the tool parser receives
empty content and the call is silently dropped. Multi-turn makes it
worse: stale assistant turns with a dangling `<think>` get re-wrapped by
the chat template on replay. Traced end to end in
[tfriedel's lab notes](https://github.com/tfriedel/qwen3.6-rtx3090-lab/blob/main/TOOL_CALLING_ISSUES.md);
vLLM fixed the parser side by treating `<tool_call>` as an implicit
reasoning end
([PR #35687](https://github.com/vllm-project/vllm/pull/35687), merged
2026-04).

**Stacks and builds bitten.** Qwen3.5-9B GGUF on llama.cpp
([#20837](https://github.com/ggml-org/llama.cpp/issues/20837), open, with
in-thread reports that Qwen3.6-35B-A3B still hits it on recent builds);
vLLM builds before PR #35687; agent stacks (Pi) whose logs show the tool
call inside the thinking field. Related vLLM streaming parser bugfixes
for the two distinct Qwen tool parsers
([#40785](https://github.com/vllm-project/vllm/pull/40785) qwen3_coder,
[#40787](https://github.com/vllm-project/vllm/pull/40787) qwen3_xml) show
the parser layer is actively moving; the failure is build-scoped.

**The check.** On forced-tool prompts, log the raw model text before any
parser, alongside the structured response. Confirmed on any turn where
raw text contains tool markup inside an open think block while structured
`tool_calls` is empty. Never conclude "cannot tool-call" from the
structured channel alone; that conclusion requires the raw dump.

**The fix.** On vLLM, run a build at or past PR #35687. On llama.cpp,
where the issue remains open, use a template that auto-closes an unclosed
`<think>` before `<tool_call>` (the froggeric and allanchan339 community
templates ship exactly this repair). In agent code, treat
stop-with-tool-markup-in-reasoning as a retryable parse failure, not task
completion.

**Found.** 2026-07-27 (mined from upstream; llama.cpp issue and vLLM fix
from the preceding months).

**Attribution.** @kik4444
([llama.cpp #20837](https://github.com/ggml-org/llama.cpp/issues/20837)),
tfriedel
([TOOL_CALLING_ISSUES.md](https://github.com/tfriedel/qwen3.6-rtx3090-lab/blob/main/TOOL_CALLING_ISSUES.md),
mechanism trace and fix evaluation), froggeric and allanchan339
(template-side auto-close repair), vLLM maintainers (PR #35687). Related
entries: [trap 02](../template/02-orphaned-think-close-tag.md) (the
mirror image: a close tag with no open),
[trap 19](19-missing-jinja-breaks-tool-parsing.md) (serve-flag half),
[trap 24](../template/24-official-template-breaks-cpp-jinja.md) (why the
community templates exist at all).

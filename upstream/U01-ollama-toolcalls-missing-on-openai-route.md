# U01: prior tool calls vanish from the rendered prompt on one of two routes

**Reported by @alejomongua.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.**

**Issue state: open** since 2025-03-17, with a reporter-authored pull request
that has not landed.

**Primary source.** [ollama/ollama#9802, "Messages[].ToolCalls not passed
correctly to the template"](https://github.com/ollama/ollama/issues/9802).
Read on 2026-07-28: issue body, the reporter's own root-cause comments, and
both maintainer replies.

**Symptom.** A multi-turn tool conversation behaves as though the model has
amnesia about its own tool calls. The assistant turn renders empty, the model
sees a tool *response* with no matching request, and it re-asks or re-calls.
A custom template with an explicit `{{ if .ToolCalls }}` branch takes the
`else` path even though the request carried a well-formed `tool_calls` array.
Nothing errors.

**Mechanism, as stated upstream.** Two things stack, and the second is the
interesting one.

The reporter root-caused it in-thread: Ollama's message handling **checks
`content` first, and does not look at `tool_calls` when `content` is
non-empty**. Frameworks that send both, the reporter names PydanticAI, which
sends `content: ""` alongside a populated `tool_calls`, fall into the gap.
Their [pull request #9834](https://github.com/ollama/ollama/pull/9834) adds the
condition for the content-plus-tool-calls case.

Maintainer @rick-github established the part that makes this a routing trap
rather than a template bug: the failure is **specific to
`/v1/chat/completions`**, and the same request through `/api/chat` renders
correctly. They posted the correct render from the native route in the thread.
@ParthSareen, also a maintainer, acknowledged the report and asked for the
native-route comparison.

There is a second incompatibility underneath. On the working route the reporter
had to pass tool-call arguments as a **mapping**, not as a JSON **string**:
which is the opposite of what the OpenAI schema specifies, and the reporter
says so plainly.

**Why this is worth an entry rather than a link.** A route-dependent difference
in what reaches the template is invisible from the API surface. Both routes
accept the request, both return 200, and the divergence is in a prompt neither
of them shows you. This registry already carries two entries whose whole
content is that one server behaves differently on two of its own routes, trap
[01](../traps/reasoning/01-reasoning-field-two-names.md) and trap
[20](../traps/reasoning/20-reasoning-write-field-name-diverges.md), and the
string-versus-mapping half is the same shape as trap
[43](../traps/template/43-tool-args-string-not-mapping.md), which we did
measure, on a different stack.

**What we have not done.** Nobody here has reproduced this. We have not run
Ollama with a custom tool-rendering template on either route, and we have not
checked whether the behaviour survives the versions since March 2025. The
issue being open is not evidence that it still reproduces; it is evidence that
nobody closed it.

## If you have this stack

Any Ollama install and any small model. The template does the work, so the
model's own tool ability is irrelevant, build one that simply echoes what it
was given.

1. Create a model whose template renders `.ToolCalls` visibly, as in the
   Modelfile in the issue: an `{{ if .ToolCalls }}` branch emitting the call
   and an `{{ else }}` branch emitting a literal marker such as
   `[NO TOOLS CALLED]`.
2. Set `OLLAMA_DEBUG=2` in the server environment so the assembled prompt is
   logged.
3. Send the **same** three-message history, user, assistant with
   `content: ""` and a populated `tool_calls`, tool result, to
   `/v1/chat/completions` and to `/api/chat`, with tool arguments as a mapping.
4. Read the two assembled prompts out of the debug log.

**CONFIRM.** The `/v1/chat/completions` render takes the `else` branch and
carries the marker, while the `/api/chat` render carries the tool call, for
identical message content.

**REFUTE.** Both routes render the tool call, or both take the `else` branch.
Both-branches-empty is a refutation of the routing claim specifically and
should be reported as such, because it would mean the divergence has been
fixed on one side or introduced on the other since the report.

**Also worth recording either way**, because the thread leaves it open: whether
the arguments-as-string form now works on `/api/chat`. If it does, the
OpenAI-incompatibility half of this report has been fixed and the entry should
say so.

## Attribution

Reported and root-caused by @alejomongua, who also opened the fix. Route
scoping by @rick-github; triage by @ParthSareen. Credited in
[HALL_OF_FAME](../HALL_OF_FAME.md).

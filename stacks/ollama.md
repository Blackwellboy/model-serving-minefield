# Ollama

**Measured here:** yes (first-party on our own hardware)


**9 entries name Ollama** in their evidence surfaces (see
[how that was counted](README.md#how-those-counts-were-derived-and-what-they-do-not-mean)):
five numbered for this stack, and four where an Ollama finding landed as an
addition to an existing entry. All of it was measured on Ollama 0.32.5 with
`qwen3:8b` on GB10 aarch64, and both the server and the model are free to
obtain, so every check below is re-derivable on your own install.

The theme of this stack is **acceptance**. A request that is wrong in almost
any way still returns HTTP 200.

## The three checks to run first

**1. Send a deliberately misspelled parameter and see whether you get a 400.**
If you get a 200, the request surface is unvalidated, your own typos are
silent, and every parameter you send is a hypothesis rather than a setting
([trap 77](../traps/reasoning/77-only-one-request-field-is-validated.md)).
Then assert on the response body rather than on the status code: two requests
at temperature 0 that differ only by the field, and identical responses mean
the field did nothing.

**2. Assert `tool_choice` actually binds before you rely on it.** Send a
tool-inviting prompt with `tool_choice: "none"` and grep the response for
`tool_calls`. It is inert in both directions on this stack, so it **fails
open** ([trap 78](../traps/tools/78-tool-choice-accepted-and-ignored.md)). The
only control that works here is not sending `tools` on that turn.

**3. Read the model's declared context before you set one.**
`/api/show` reports `context_length`; assert you are under it. An out-of-range
request returns 200 with empty content and no clamp message, and raising the
output budget does not fix it
([trap 79](../traps/memory/79-out-of-range-context-request-accepted.md)).

## The five that bite hardest here

| Entry | What it does to you |
|---|---|
| [77, one request field is validated and every other one you invent is accepted](../traps/reasoning/77-only-one-request-field-is-validated.md) (**Core**) | A harness ported from another server sends `enable_thinking: false`, gets 200, and measures its entire thinking-off arm on a thinking lane |
| [78, `tool_choice` is accepted and ignored](../traps/tools/78-tool-choice-accepted-and-ignored.md) | The standard way an agent framework gates a turn fails open, on both the native and the OpenAI-compatible route |
| [01, three reasoning names on one server, split by route](../traps/reasoning/01-reasoning-field-two-names.md) (**Core**) | `message.thinking`, a top-level field, and `message.reasoning` depending on the route. `reasoning_content` exists on none of them, so a client written against a vLLM lane reads zero |
| [79, an out-of-range context request is accepted](../traps/memory/79-out-of-range-context-request-accepted.md) | HTTP 200, empty content, and a context size the model could never have honoured |
| [76, the alarming startup line that did not matter](../traps/runtime/76-device-rejection-log-line-is-not-fatal.md) | One bundled runner rejects the card at INFO before a later one accepts it. The expensive version is a health check that greps for the string and fires on every healthy start |

## Also worth knowing on this stack

- [66's injection mirror](../traps/template/66-in-text-thinking-toggle-mutates-user-text.md#the-mirror-case-injection-on-ollama):
  the template appends the in-text thinking marker to the last user message
  and it leaks into output, breaking exact-match scoring.
- [75](../traps/versioning/75-release-asset-renamed-pinned-url-404.md): a
  pinned install URL that worked for months returning 404, because the release
  asset was renamed and the archive format changed.
- [12](../traps/evaluation/12-empty-content-at-token-ceiling.md) and
  [04](../traps/template/04-history-reasoning-stripping.md) were both confirmed
  on this stack.
- The real thinking control here is `think` on the native API and
  `reasoning_effort: "none"` on the `/v1` route, not the kwarg name that works
  elsewhere.

## A negative from the same pass

The candidate "thinking plus tools yields empty output" was
[refuted as stated](../mining/2026-07-27-r2-39-thinking-plus-tools-not-reproduced-on-vllm.md#update-2026-07-28-tested-on-ollama-refuted-as-stated-and-re-scoped)
on the stack it had been scoped to. Empty content tracked tools alone and
every empty response carried a tool call: that is a harness reading `content`
and ignoring `tool_calls`, not a defect.

# U18: an explicit empty `tool_calls` array can make a client hide valid streamed text

**Reported by @hhackbarth.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The parser fix was reviewed and merged into the source recipe.

**Issue state: closed, fixed.** PR #17 is merged.

**Primary source.** [tonyd2wild DeepSeek-V4-Flash PR #17](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark/pull/17), read on 2026-08-21.

**Symptom.** Tool calls work, reasoning is present, and the model streams a complete answer, but an agent client displays no answer at all. In the reported VS Code case, a complete 2,135-character reply existed on the wire while the client rendered "Sorry, no response was returned."

**Mechanism.** The affected DeepSeek V4 parser inherited a streaming branch that explicitly constructed `DeltaMessage(content=..., tool_calls=[])` on ordinary text deltas whenever the request carried tools. With `exclude_unset=True`, explicitly setting the empty list puts `"tool_calls": []` on the wire. JavaScript treats an empty array as truthy, so a client shaped like `if (delta.tool_calls) { ... } else if (delta.content) { ... }` routes every content delta down the tool-call branch and never renders the text.

The contributor reported 232 of 232 content deltas carrying the explicit empty field when tools were present; without tools the field was absent. Real tool-call parsing and arguments were unchanged by the fix.

**What we have not done.** We have not run the affected parser or VS Code client ourselves. This entry does not claim every OpenAI-compatible client mishandles `tool_calls: []`; the failure requires a client whose branching semantics distinguish absent from explicitly empty incorrectly.

## If you have this stack

Capture raw SSE from the same prompt twice, once with a tool schema attached but no tool needed and once without tools. Inspect whether ordinary text deltas explicitly include `tool_calls: []`. Feed the exact stream to the client that appears blank, then patch the parser to leave `tool_calls` unset on content-only deltas and repeat.

**CONFIRM.** Content-only deltas carry explicit `tool_calls: []`, the affected client routes them away from its text renderer, and omitting the unset field restores the visible answer without changing real tool calls.

**REFUTE.** The allegedly affected build does not emit the empty field, or the client renders identical text whether the field is absent or an empty array.

## Attribution

Reported and measured by @hhackbarth in PR #17; the source recipe maintainer merged the parser correction. The registry has not independently reproduced it.

# U12: the stream is HTTP 200 before the request has even passed validation

**Reported by @aiwantaozi.**

**Status: upstream-reported.** Nobody here has reproduced this.

**Maintainer engagement: maintainer confirmed.** The issue was assigned, a fix was developed, and the final regression fix was merged upstream.

**Issue state: closed, fixed.** The final fix is SGLang PR [#21900](https://github.com/sgl-project/sglang/pull/21900), merged 2026-04-02.

**Primary source.** [sgl-project/sglang issue #19996](https://github.com/sgl-project/sglang/issues/19996) and merged [PR #21900](https://github.com/sgl-project/sglang/pull/21900), read on 2026-08-14.

**Symptom.** An oversized OpenAI-compatible chat request is rejected differently depending only on streaming mode. The non-streaming request returns HTTP 400. The same invalid request with `stream=true` returns HTTP 200, then carries an error object whose internal code says 400.

A client that treats the initial status as the request verdict records a successful HTTP call even though generation was never valid. A benchmark or agent harness can therefore count a transport-level pass for a request the server rejected.

**Mechanism, as fixed upstream.** The streaming handler constructed and returned `StreamingResponse` before its async generator had reached request validation. Once the response started, HTTP 200 was committed. A later validation failure could only be serialized inside the SSE stream.

The merged fix kick-starts the generator before returning `StreamingResponse`. If validation fails before the first chunk, the handler can still return an ordinary HTTP 400. The PR adds a streaming over-context regression test alongside the existing non-streaming validation coverage.

**Why this is worth an entry.** Streaming changes the point at which transport status becomes irreversible. That means `response.status_code == 200` is not a sufficient success assertion on an affected streaming API. This is adjacent to [Trap 16](../traps/evaluation/16-finish-reason-is-not-a-failure-signal.md): both are cases where one convenient response field is not the verdict you think it is, but this one happens before generation and is specific to streaming error transport.

**What we have not done.** We have not run an affected SGLang build or reproduced the before/after behavior. The fixed state comes from the upstream issue and merged regression PR.

## If you have this stack

Use an SGLang build from before the merged fix and a current fixed build. Send one prompt that is definitely longer than the configured context length twice: once with `stream=false`, once with `stream=true`. Capture both the HTTP status and the first SSE/body payload.

**CONFIRM.** On the affected build, non-streaming returns HTTP 400 while streaming returns HTTP 200 and then an error payload. On the fixed build, both reject before a successful stream is established.

**REFUTE.** The allegedly affected build returns the same HTTP error status for both modes. Record the exact SGLang revision because this entry is version-bounded by an upstream fix.

## Attribution

Reported by @aiwantaozi in SGLang issue #19996. Final merged fix in PR #21900 by @hnyls2002 and SGLang maintainers/contributors.

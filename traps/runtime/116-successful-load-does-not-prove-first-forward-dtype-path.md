# Trap 116: successful model load does not prove the first-forward dtype path

**Found by Blackwellboy** (external multi-node hardware qualification of a
distributed serving stack). Patch author for the F16 embedding path:
**Victor Cruz / vcruz305**.

**Status: contributor-measured, conditions as reported.** Distributed load
and first-forward sequence on a multi-rank bring-up; private hosts, paths,
and raw logs scrubbed. Mechanism is general: load success is not first-forward
dtype-path success.

**Symptom.** Multi-rank load reports success on every rank (for example three
of three ranks "loaded ok"). The first forward then fails with an embedding /
token-embedding helper error such as `forward: embed_token failed` under an
F16 (or other non-default) representation path. Operators conclude the
checkpoint is corrupt, the transport is broken, or the model is "not
supported", and restart or redownload.

**Mechanism.** Model **load** and **first forward** are different capability
gates. A stack can materialize weights into device memory, pass LoadReady-class
signals, and still fail when the first forward enters a dtype-specific helper
(here: the F16 embedding / `embed_token` path) that was not exercised by load.

Chronology that must stay accurate (sanitized, public-safe):

1. **Observation A (load ok, forward fail).** All ranks complete a real model
   load, then fail deterministically on first forward in the F16 embedding path
   (`embed_token failed` class). Generated-token count is zero for that
   attempt.
2. **Observation B (author F16 patch applied).** After the author-supplied F16
   patch, all ranks load again; the **old failure string is absent**. That is
   **not** independent proof that first forward completed: generation
   completion and embed-path success were not yet proven under instrumentation.
3. **Observation C (instrumented proof).** Author instrumentation shows, on
   all ranks: embed_token enter/ok, first attention collective enter/ok,
   full layer stack completion, and a short prompt+decode generation
   completing. Only then is the F16 fix **runtime-confirmed**.

Research-integrity lesson: **absence of the old error is not proof that the
corrected boundary completed.**

**What the tempting diagnosis gets wrong.**

- Treating "3/3 load ok" as "serve is ready to generate".
- Treating "old error string gone" as "forward/generate PASS".
- Blaming model corruption or fabric when the failure is a post-load
  dtype/helper path.
- Crediting the wrong author for the patch chain, or omitting the external
  hardware-qualification role.

**Stacks and builds bitten.** Multi-rank distributed serving where load and
first forward are separate stages, especially when non-default dtypes or
custom embedding helpers are in play. Observed during Spark-class multi-node
qualification of an author-maintained serving path (sanitized).

**The check.**

1. After load success, issue a **bounded first-forward / short generate** before
   declaring the serve healthy.
2. If first forward fails in an embed/dtype helper, record load success and
   forward failure as **separate facts**.
3. After a candidate fix, require **positive proof** of the corrected boundary
   (instrumented enter/ok or completed decode), not only absence of the prior
   error string.
4. Keep attribution: patch author vs hardware qualifier.

Related readiness hierarchy: [112](112-process-liveness-is-not-model-readiness.md)
(resident != first forward != generation complete).

**The fix.** Ensure the F16 (or other) embedding/helper path is exercised and
supported for the loaded representation; land author-maintained patches that
make that path complete; verify with instrumentation or a short generation
that proves embed + decode, not merely a clean log for the old error.

**Claim boundary.**

- May claim: successful load does not prove first-forward dtype/helper support;
  absence of an old error is not completion proof; FIX was runtime-confirmed
  only under instrumented observation C.
- Must not claim: model weights were corrupt; Blackwellboy authored Victor's
  patches; private host details; a measured multi-tok/s production rate for
  unproven future draft-model work; that observation B alone was a generate
  PASS.

**Found.** 2026-08 multi-rank distributed bring-up sequence (sanitized public
derivative of private campaign receipts 0008/0009/0010).

**Attribution.**

- **Victor Cruz / vcruz305** — author of the F16 embedding patch chain and
  instrumentation used for runtime proof.
- **Blackwellboy** — external multi-node (3x DGX Spark class) hardware
  qualification and evidence adjudication; not the patch author.

**Related.** [112](112-process-liveness-is-not-model-readiness.md),
[115](../evaluation/115-exit-137-is-not-oom-killer-proof.md) (separate
failure-cause claims).

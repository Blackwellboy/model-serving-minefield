# Qwen3.8 Offlabel reconciliation — 2026-08-17

This note records the public-safe disposition of Minefield issue #40 against
current canonical ownership. It does **not** create a canonical trap ID by
itself.

## Source and evidence boundary

External source: TheTom/Offlabel Qwen3.8 guide and public discussion cited in
issue #40. First-party Qwen3.8 observations are kept build/config scoped. A
public-source observation is not upgraded to reproduced-here merely because a
related first-party mechanism exists elsewhere.

## A — `reasoning_effort=medium`

**Disposition: incorporated / existing Trap 07 extension.** The current
Qwen3.8 template accepts `medium` while lacking a dedicated medium instruction
branch. PR #41 already incorporated the reproduced template behavior. No new
trap ID.

## B — `preserve_thinking`

**Disposition: incorporated / Trap 04 + Trap 25 family.** Replayed reasoning
can enlarge later prompts; empty wrappers and premature-abort claims remain
separate questions. PR #41 already incorporated the reproduced boundary. No
new trap ID.

## C — `finish_reason=length`

**Disposition: Trap 16 extension.** A public Qwen3.8 report shows that `length`
may reflect total server-context exhaustion rather than exhaustion of the
requested output cap. Minefield's content-first rule is unchanged. The
confirmation receipt should include prompt/input tokens, configured context,
requested output budget, completion tokens and remaining headroom. The public
source observation is recorded in Trap 16 without claiming first-party
reproduction.

## D — SM121 NVFP4 backend coherence

**Disposition: unverified lead, build-scoped.** The public report says one GB10
/ SM121 vLLM NVFP4 path was incoherent under its default backend and coherent
when a Marlin path was requested. A separate first-party Qwen3.8 check showed
why request flags alone are insufficient: on that tested build the requested
Marlin environment controls were not recognized and the effective backend
remained FlashInferCutlass.

The useful Minefield diagnostic is therefore:

1. pin the exact image/build and model revision;
2. prove the **effective** kernel/backend from runtime evidence;
3. run identical correctness canaries on both arms;
4. only then compare speed or coherence.

Until that same-build A/B exists, keep the source claim
`PUBLIC_SOURCE_UNREPRODUCED`. Related canonical owners: Traps 09, 10 and 27.

## E — Qwen3.8 speculative launch can fail at hybrid state-cache admission

**Disposition: existing admission ownership / L003 + Trap 98 family.** A
first-party Qwen3.8 RTX 5090 lane reached non-spec serving while tested MTP and
DSpark configurations failed during hybrid Mamba/linear-attention state-cache
admission. That is a resource/build/config boundary, not evidence that “Qwen3.8
MTP is unsupported.”

The bounded confirmation check is to record model weights, fixed reservations,
hybrid-state request, remaining memory and the pass/fail admission boundary.
If a controlled memory profile admits the same speculative path, the original
failure was admission pressure, not a model-capability failure.

## F — substring canaries can manufacture a false PASS

**Disposition: evaluation-methodology / check-discipline, not a new serving
trap.** A canary that tests only `sentinel in response_text` can pass when the
sentinel appears in reasoning, prompt echo or a truncated response without the
requested final answer.

Required regression:

- normalize and compare the **final answer surface** exactly;
- reject exact-answer canaries that terminate by truncation;
- exclude reasoning/prompt echo from final-answer scoring;
- include a known-bad fixture that contains the sentinel outside the answer
  surface and must fail.

This belongs with Minefield's false-healthy / “the check that did not check”
methodology material. It should not be promoted as a model-serving defect.

## Linked intake

- #35 remains contributor-owned and requires current-main rebase/renumbering;
  do not copy its implementation.
- #36 remains a distinct canonical candidate with its own credit/evidence path.
- #37 is reconciled to existing ownership: Trap 54 plus Traps 13/119 and
  measurement guidance; no new canonical ID.
- #38 remains a distinct canonical candidate with its own credit/evidence path.

## Close condition for #40

Close the umbrella only after this source wiring, the lead catalogue mirror and
all generated full/lite/JSON surfaces pass the repository's deterministic
integrity checks. Canonical count remains unchanged by this reconciliation.

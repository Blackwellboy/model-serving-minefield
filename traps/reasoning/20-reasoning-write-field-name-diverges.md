# Trap 20: the reasoning write field is runtime-specific

**Found by @Defilan.**

**Status: reproduced by @Defilan on llama.cpp** (deterministic render probe,
byte-for-byte); **our vLLM side reproduced here** (passthrough verified by
prompt_tokens). Behavioral effect on llama.cpp is under test by @Defilan,
who has committed to report the result either way.

**Symptom.** You implement trap 04's fix: resend prior-turn reasoning on
assistant messages so the template renders real think blocks. You re-render,
and the history is still stripped: empty `<think></think>` on every prior
turn, byte-identical to not resending anything. You conclude the fix is
wrong, or that trap 04 "does not reproduce" on your stack. The number that
follows is a stripped-arm number wearing a preserved-arm label.

**Mechanism.** Which key of an assistant message reaches the chat template
differs by runtime, and a wrong key is silently dropped rather than
rejected:

- **llama.cpp**: only `reasoning_content` is mapped into the template
  context. `reasoning` is dropped, and the render is byte-identical to the
  stripped arm.
- **vLLM** (0.25.1, this model's parser): `reasoning` passes through to the
  template. Verified by prompt_tokens moving 63 to 303 with ~200 tokens of
  reasoning attached.

This is trap 01 one layer down. Trap 01 is *reading* the reasoning field
under the wrong name; this is *writing* it under the wrong name. The read
side and the write side have different correct answers on the same two
runtimes, and both fail silently by producing absence: no error, no
warning, just a render or a parse that looks like the model did not think.

**Stacks and builds bitten.** llama.cpp serving Laguna S 2.1 Q4_K_M
(Vulkan on gfx1151, poolside GGUF with the corrected fork template),
probed by @Defilan via `/apply-template` so the render is deterministic and
repeats byte for byte: same transcript preserved via `reasoning_content`
gives three filled think blocks (+180 chars); preserved via `reasoning`
gives a render byte-identical to the stripped arm. vLLM 0.25.1 serving
Laguna S 2.1 NVFP4: `reasoning` passes through (ours). A wrong-field
implementation is invisible on vLLM and fatal on llama.cpp; a correct
llama.cpp implementation ported to a stack that only reads `reasoning`
would fail the same way in reverse.

**The check.** Probe both field names on your lane, same transcript,
before trusting either. Render a conversation whose prior assistant turn
carries a uniquely marked reasoning string once under `reasoning` and once
under `reasoning_content`, and diff the two renders (llama.cpp's
`/apply-template` makes this deterministic; on other runtimes compare
prompt_tokens and grep the assembled prompt for the marker, as in
[checks/preflight_template.py](../../checks/preflight_template.py)). The
arm whose render contains the marker is your write field. If neither does,
you are in trap 04 with no preservation path and need the kwarg route.

**The fix.** Name the field per runtime; do not port the fix by copying
the field name from someone else's writeup. On llama.cpp, resend prior
reasoning as `reasoning_content`. On vLLM with this model's parser, resend
`reasoning`. For tooling authors the shape from trap 04 still holds: an
explicit per-provider capability flag for echo-reasoning-on-replay, with
the field name part of the per-provider capability, not a constant.

**Found.** 2026-07-27, in @Defilan's cross-stack replication of trap 04
([offlabel #16](https://github.com/TheTom/offlabel/issues/16#issuecomment-5086926968)).

**Attribution.** @Defilan (the llama.cpp write-side probe and the
divergence finding, plus the stateless-history discipline that kept the
comparison clean); Blackwellboy (the vLLM passthrough half). Related:
[trap 01](01-reasoning-field-two-names.md) (read side),
[trap 04](../template/04-history-reasoning-stripping.md) (why the write
matters at all).

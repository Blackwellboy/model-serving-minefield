# Trap 68: content-part order is discarded and adjacent text parts are glued together

**Found by Blackwellboy.**

**Status: reproduced here, with the reversed-order control rendering byte for
byte identical.**

**Symptom.** A prompt that puts an instruction before an image and a constraint
after it behaves as if the constraint were somewhere else. Interleaving several
media items with commentary produces answers that mix them up. No error is
raised, and the request is a well-formed content-part array.

**Mechanism.** The template counts the media parts, emits **all** the
placeholders first, then appends **every** text part concatenated in order. The
position of media relative to text is discarded before the model sees it.

```
request : [text "FIRST_TEXT_MARKER", image]  ->  <img>...</img>\nFIRST_TEXT_MARKER
request : [image, text "FIRST_TEXT_MARKER"]  ->  identical, token for token
request : [text "ALPHA_MARKER", image, text "OMEGA_MARKER"]
                                            ->  <img>...</img>\nALPHA_MARKEROMEGA_MARKER
```

Two separate defects in one pass. The **ordering** loss is the one people notice
eventually. The **concatenation** is the one that silently corrupts text:
`ALPHA_MARKER` and `OMEGA_MARKER` are joined with no separator at all, so the
last word of one part and the first word of the next run together into a token
sequence neither of them contains.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Nano Omni 30B A3B Reasoning
NVFP4, vLLM 0.20.0 upstream arm64 container, single GB10-class node. Verified
against the assembled prompt, not inferred from answers.

**The check.** Render `[text A, image, text B]` and `[image, text A, text B]` and
compare the assembled prompts. If they are identical, order is discarded. Then
look for `AB` with no separator between them, which is the concatenation half.
The registry doctor now performs both checks on any lane that accepts an image
part.

**The fix.**

1. Put positional information **in the text**, not in the arrangement: "the image
   above", "answer using only the image", "the first image shows". The model
   cannot see your arrangement.
2. Separate adjacent text parts yourself with an explicit newline or delimiter,
   or merge them into one part client-side before sending.
3. For multi-image prompts where "which image" matters, label them in text.
   Placeholder order is preserved among themselves; only the interleaving with
   text is lost.

**If you miss it.** Any result about instruction placement, about
before-versus-after framing, or about multi-image reasoning is measured on a
prompt the model never received in that form. And a fraction of your text is
subtly corrupted by the concatenation, which will show up as inexplicable
tokenisation artefacts rather than as an obvious error.

**Negatives recorded.**

- Media placeholders keep their order relative to each other; it is only the
  text-versus-media interleaving that is lost.
- The response is normal and the request validates. There is no error to catch.

**Related.**
[trap 04](04-history-reasoning-stripping.md) and the
[object-repr draft](67-history-rendered-as-object-repr.md) are the other two
ways this family's templates corrupt a well-formed request without raising
anything. All three are found the same way: render the prompt and read it.

**Found.** 2026-07-27.

**Attribution.** Blackwellboy.

# Trap 74: out-of-domain audio is answered with confident captions from a memorised annotation schema

**Found by Blackwellboy.**

**Status: measured here, raw not published.** Five inputs of exactly known
ground truth, multiple transports, repeated runs, and both reasoning modes.
The audio files and the responses are not published, so this is a model
behaviour a stranger has to re-observe rather than check. Scoped to non-speech
audio; speech was not tested, and the entry does not generalise past that.

**Symptom.** An audio pipeline returns fluent, specific, confident descriptions
of every clip you send it. Spot-checking a few against real recordings looks
fine. Then someone sends silence and gets a detailed description of a keyboard
note.

**Mechanism.** Presented with audio outside its training domain, the model does
not refuse, hedge, or return an empty answer. It emits a caption in a **memorised
annotation schema**, phrased as fact. The vocabulary is the giveaway: pitch,
velocity, source and quality fields belong to a musical-instrument annotation
format, and a second set of answers are environmental-audio captions. Neither has
any relationship to the input.

| Input, exact ground truth | Question | Answer |
|---|---|---|
| three 1-second sine tones at 440, 660 and 880 Hz | how many distinct tones, one digit | `1` (four runs, both transports, and again with reasoning on after 853 tokens of trace) |
| the same file | describe what you hear, is there any speech | "a note that is produced by mallet, pitch 56, velocity 127, source electronic, and having qualities like bright, distortion, long release, nonlinear env" |
| the same file | transcribe this audio | "a note that is produced by mallet, pitch 57, velocity 127 ..." |
| amplitude-modulated noise | describe this sound | "The sound of holding the cloth with both hands." |
| **two seconds of digital silence** | describe this sound | "a note produced by keyboard, pitch 45, velocity 100, source electronic, and having qualities like dark" |

Note the tone-counting row. Reasoning on, 853 tokens of deliberation, same wrong
answer. More thinking did not help, which rules out an under-computation
explanation.

Note also that a **transcription** request against non-speech audio is never
refused and never returns an empty or hedged result. It returns a caption in the
wrong schema.

**Scope limit, stated plainly and kept in the entry.** No speech sample with a
known transcript was available offline, so speech recognition, which is the
advertised strength of this audio path, was **not** tested. This entry does not
establish that transcription of real speech is wrong. It establishes that the
audio path has no out-of-domain refusal and fabricates confidently when it is out
of domain. Those are different claims and only the second one is supported here.
Anyone extending this should add a speech clip with a known transcript first;
that result decides which of the two headlines is correct.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Nano Omni 30B A3B Reasoning
NVFP4, vLLM 0.20.0 upstream arm64 container, single GB10-class node, Parakeet
audio encoder at 16 kHz. All test assets were generated from constants in the
session's own driver, so ground truth is exact rather than judged.

**The check.** This is cheap and everyone with an audio lane should run it.
Generate three files with a few lines of code: two seconds of digital silence, a
few distinct pure tones, and band-limited noise. Ask the lane to describe and to
transcribe each. **Any confident, specific answer to the silence file is a
failure.** The correct behaviours are a refusal, a hedge, or an empty result.

Add a real speech clip with a known transcript as the fourth file, and you have a
complete audio smoke test that distinguishes "cannot transcribe" from "will not
admit it".

**The fix.** There is no server-side fix; this is model behaviour.

1. **Gate on input domain.** Run cheap voice-activity or energy detection before
   sending audio, and do not send clips with no speech to a transcription path.
2. **Never treat an audio caption as evidence.** Do not let one enter a downstream
   pipeline as a fact, and do not include one in a history that a later turn will
   reason over.
3. **Include silence in your evaluation set.** A model that describes silence will
   describe anything, and the only way to know is to send nothing and see what
   comes back.
4. If you report any audio quality number for this model, state whether your
   inputs were in domain, because the failure is entirely on the out-of-domain
   side.

**If you miss it.** Every non-speech input in your corpus produces a plausible
false label, at a rate that depends on your corpus and that no confidence signal
will reveal. Human review will not catch it either, because the answers are
fluent and specific.

**Negatives recorded.**

- **Image and video understanding on the same lane were accurate throughout**:
  exact OCR of five lines, exact values for all four bars of a chart, correct
  object and window counts, correct text out of a 5000 by 5000 pixel input, and
  four video segments with correct numbers, colours and order in both reasoning
  modes. This is not a general multimodal-competence finding. It is specific to
  the audio path and to out-of-domain audio within it.
- Reasoning on does not fix it, so it is not a budget or effort problem.
- Both transports (inline data URL and file path) produce the same answers, so it
  is not a decoding artefact of one path.

**Related.**
[trap 34](34-baseline-you-degraded-yourself.md) and
[trap 37](37-uniform-zero-is-a-harness-verdict.md) are the neighbouring
"your measurement is measuring something else" entries. This one is the inverse
shape: the harness is fine and the model is confidently wrong in a way that
scores as an answer.

**Found.** 2026-07-27.

**Attribution.** Blackwellboy.

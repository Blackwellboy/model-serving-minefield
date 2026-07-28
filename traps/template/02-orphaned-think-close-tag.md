# Trap 02: orphaned `</think>` leaking into content

**Found by Blackwellboy.**

**Status: reproduced here** on two serving stacks (EXL3-tail container and venv vLLM 0.25.1, same parser).

**Symptom.** Every response arrives with a stray `</think>` at the very start
of `content`. It renders fine in a chat window and breaks everything
downstream: prefix matching, JSON extraction, first-line parsing, diffing. It
also inflates or deflates content-length metrics by a constant, which is the
kind of error that survives review because it looks like a small consistent
offset.

**Mechanism.** A reasoning parser that strips the opening `<think>` of an
empty think block but not the closing tag. On this stack it triggers whenever
the `enable_thinking` kwarg is **absent** from the request and the model
emits an empty think block (absent means ON for this revision, but low-firing
task shapes skip thinking, producing the empty block).

**Stacks and builds bitten.** First seen on a 3.25bpw EXL3-tail hybrid
container serving Laguna S 2.1 with the `poolside_v1` reasoning parser, every
single response, and initially attributed to that container's configuration.
That attribution was wrong: a full-precision spine run reproduced it on a
venv-served vLLM 0.25.1 lane with the same parser. It is
`poolside_v1`-on-vLLM behavior, not a container bug. With the kwarg absent it
appeared in 42/42 non-firing spine rows on both serving stacks; with the
kwarg explicit it appeared in 0/984 A/B rows.

**The check.** Assert that `content.lstrip()` does not start with
`</think>`, and that open and close tag counts in the response are balanced.
In an assembled prompt, expect exactly one dangling open `<think>` at the end
(the generation prompt) and treat any excess of closes as this trap.

**The fix.** Send `enable_thinking` explicitly, either value. With the kwarg
explicit the artifact did not appear in any of 984 rows.

**Found.** 2026-07-26, quant-floor verification of the hybrid quant.
Re-attributed 2026-07-27 after the full-precision reproduction.

**Attribution.** Blackwellboy. Raw data:
[quant-floor/](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/quant-floor),
[spine-probes/fullprecision/](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/spine-probes/fullprecision),
[pr10-replication/](https://github.com/Blackwellboy/laguna-s21-lab/tree/main/pr10-replication).

## Added 2026-07-28: the parser-less default on a current family

**NVIDIA Nemotron 3 family, three checkpoints (Nano 30B A3B NVFP4, Nano Omni 30B A3B NVFP4, Super 120B A12B NVFP4), GB10-class single nodes, vLLM 0.20.0 and 0.25.1.** Served with no `--reasoning-parser`, `content` carries the full
reasoning text, then a bare `</think>`, then the answer, with **no opening
`<think>`**, because the template pre-opens the block in the prompt and the
model only ever emits the closer. That is
[trap 38](38-template-owns-the-opening-think-tag.md)'s mechanism producing this
entry's symptom, which is worth seeing once in one place.

Confirmed on both text-only members; the saved control-server response is 1370
completion tokens with the reasoning half sitting in `content` ahead of a lone
`</think>`.

These checkpoints ship their own reasoning parser inside the model repository,
which is [its own entry](../runtime/70-in-repo-parser-not-bundled.md). Without
mounting it, the above is the default experience.

*Status of this addendum: reproduced here. The pre-opened block is in the
public chat template and the parser-less arm is one serve flag away on any
lane.*

# Trap 02: orphaned `</think>` leaking into content

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

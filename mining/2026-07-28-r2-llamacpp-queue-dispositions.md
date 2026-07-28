# R2 queue: the blocked llama.cpp candidates, adjudicated

**Date:** 2026-07-28. All five tested on llama.cpp `b9878-2da668617` serving a
Mistral-family Q8_0 GGUF of unstated provenance, supplied by **Exile** for stack
coverage. Two consumer GPUs of different architectures in one host. Every
finding is scoped either to that artifact or, where the mechanism is
server-side, to the build. No capability claims; refusal behaviour and
guardrails were not probed and are not discussed.

These candidates were all queued as "needs a llama.cpp lane" and deferred. The
lane existed for one session; this is what came of it.

| Candidate | Verdict | Where |
|---|---|---|
| R2-16 multi-slot continuous batching non-determinism | **CONFIRMED HERE, with a length floor that inverts the usual reproduction** | [trap 91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md) |
| R2-17 timestamp in system prompt kills the prefix cache | **REFUTED AS WORDED; mechanism confirmed at a different position; the received mitigation is inverted** | [trap 93](../traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md) |
| R2-41 shared system prompt across slots changes determinism | **CONFIRMED HERE, and resolved into two separable causes** | [trap 91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md) and [trap 92](../traps/runtime/92-prompt-cache-is-a-second-divergence-source.md) |
| R2-46 partial GPU offload misread as slowness | **CONFIRMED HERE and stronger than claimed: no endpoint names the split** | [trap 97](../traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md) |
| R2-18 llama.cpp cache and unified-memory reporting nonsense | **NO LONGER BLOCKED for the reporting half**, reproduced on WSL2 rather than on unified-memory hardware. Cache-sizing half untested, still open | [trap 96](../traps/memory/96-list-devices-reports-host-memory-as-device-free-memory.md) |

## R2-16 and R2-41 were the same question, and the queue was right to keep both

R2-16 asked whether multi-slot batching perturbs output. R2-41 asked whether a
*shared system prompt* across slots does. Tested separately they gave opposite
first answers: a short no-system-prompt request was byte-identical in 16/16
concurrent responses, while the same request behind a shared 365-token system
prompt produced 3 distinct outputs in 8. Taken alone, R2-16 reads refuted and
R2-41 reads confirmed.

They are one effect with a **prompt-length floor**. Once length is swept, the
picture resolves: 108 to 136 token prompts never diverge (0/256 responses), 220
and longer prompts do. The shared system prompt in R2-41 was not special for
being shared or for being a system prompt. It was special for being *long*.

**The consequence for anyone reproducing R2-16 is a false negative**, because
the natural minimal reproduction is a short prompt. That is the most
transferable thing this pass produced and it is why
[trap 91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md)
is the entry to read.

A second, independent cause was separated out along the way: with the prompt
cache at its default, divergence also appears at **concurrency 1**, tied to
partial cache hits. `cache_prompt: false` removes it and leaves the batching
effect standing. Any future work on either candidate should disable the cache
first or it will measure both at once. That is
[trap 92](../traps/runtime/92-prompt-cache-is-a-second-divergence-source.md),
along with a self-caught error where cache retention across arms reversed the
sign of a result.

## R2-17 was worth an entry rather than a quiet close

The candidate's mechanism is real: a per-turn clock at the head of the prompt
took prefix reuse from 474 tokens to 4, and prefill from 82 ms to 216 ms. But
its *stated position*, the head of the system prompt, is inert on this template,
136 against 135 cached tokens, because the template relocates the system block
to the last user turn.

That makes the received advice a no-op and the received alternative harmful:
moving volatile text from the system prompt into the first user message is
precisely the change that destroys reuse here. A refutation that stopped at "we
could not reproduce it" would have left the inverted mitigation in circulation,
which is why this landed as
[trap 93](../traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md)
rather than as a closed candidate. Note that the advice being corrected is
received wisdom in the wild, not something this registry has ever published:
no entry here has recommended it.

## R2-27 stays closed, and this pass is the reason it can be stated firmly

Recorded here because the fourth-stack pass already corrected it and this
session confirms the correction from the other direction: the Mistral
tokenizer-mode candidate is **llama.cpp-inapplicable**, not weight-blocked. This
session served a Mistral-family GGUF on llama.cpp, exactly the artifact the
original blocker implied was missing, and still could not test it, because the
flag is hard-rejected by the binary and GGUF conversion discards the tokenizer
the flag selects. A Mistral checkpoint arriving does not unblock it. It remains
open only against a stack that implements the flag. See
[the blocked-candidate note](2026-07-27-r2-blocked-not-testable.md).

## Still blocked on this queue

Unchanged by this pass, and stated so nobody reads a llama.cpp session as having
cleared them: the VL reranker candidate (no reranker or VL weights), the SGLang
candidates (SGLang not installed on the nodes available to this session), and
the cache-sizing half of R2-18. The remaining llama.cpp-tagged candidates not
listed in the table above were out of this session's scope and were **not**
examined. They are neither confirmed nor refuted here.

## Coverage that was not asked for and came out of the same lane

Two entries in this batch are not R2 candidates at all. Both exist because the
session had two GPUs of different architectures in one host, which is a
configuration the registry had never exercised:

- [Trap 94](../traps/runtime/94-temp0-reproducibility-is-architecture-dependent.md):
  temperature-0 reproducibility under concurrency holds on `sm_86` and fails on
  `sm_120`, same binary, same weights. The hardware axis is real, and a claim
  scoped to one architecture is not automatically a claim about another.
- [Trap 95](../traps/runtime/95-two-gpu-co-tenancy-does-not-perturb-either-lane.md):
  a **negative**. Co-tenancy of two lanes on two GPUs of one host perturbs
  neither correctness nor decode throughput.

**Credit.** Exile supplied the target and did not label it; the scoping
throughout this batch is what that honesty is owed. TheTom's parallel-slot
context entry, [trap 46](../traps/versioning/46-stale-build-missing-arch-kernel.md),
is the prior art the `-np` and context behaviour here sits on.

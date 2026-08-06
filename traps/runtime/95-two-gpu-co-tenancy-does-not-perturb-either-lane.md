# Trap 95: two llama.cpp lanes on two GPUs of one host do not perturb each other's correctness or decode throughput

**Found by Blackwellboy.** Target supplied by Exile.

**Status: measured here, raw not published**, and it is a **negative result**.
2026-07-28, llama.cpp `b9878-2da668617` serving one Mistral-family Q8_0 GGUF of
unstated provenance from two independent server processes, one pinned to each of
two consumer GPUs in a single host (`sm_120` and `sm_86`),
`-c 32768 -np 4 -fa on --jinja`, both with memory headroom (20196 MiB and 12610
MiB free after load).

**Evidence pointer.** The same two probes run twice: once with the neighbour
loaded but idle, once with both lanes driven simultaneously. The procedure is
reproducible on any two-GPU host; the medians below are ours and are not shipped.

**Symptom.** You are about to attach a co-tenancy caveat to a number, or to stop
sharing a host, on the belief that two models on one box interfere. On this
configuration they do not, and the caveat would be unearned.

## Why record a negative

"Two models on one box evict each other" is a common enough belief to be worth
either confirming or killing, and it is expensive to test anywhere that does not
already have two different GPUs in one chassis. A null here is a load-bearing
null: it means single-GPU measurements taken on a shared host do not need a
co-tenancy caveat attached, which removes a standing doubt from every number we
have taken on a multi-GPU box.

## Decode throughput: no effect

Median server-reported decode rate, n=6 requests per cell, `cache_prompt: false`:

| lane | neighbour idle | neighbour generating | change |
|---|---|---|---|
| `sm_120` | 158.75 tok/s | 158.06 tok/s | -0.4% |
| `sm_86` | 82.55 tok/s | 82.81 tok/s | +0.3% |

Both changes are inside the spread of the individual samples, which ran
151.7 to 162.3 and 79.6 to 83.2 tok/s respectively. No decode effect.

## Correctness: no effect

Divergence rates were measured under both conditions using the concurrency
sweep described in
[trap 91](91-concurrency-nondeterminism-has-a-prompt-length-floor.md), 2
replicates each, `cache_prompt: false`:

| lane | prompt tokens | cells diverging, neighbour idle | cells diverging, both busy |
|---|---|---|---|
| `sm_120` | 220 | 2/2 | 2/2 |
| `sm_120` | 444 | 2/2 | 2/2 |
| `sm_120` | 1900 | 2/2 | 2/2 |
| `sm_86` | 220 | 2/2 | 2/2 |
| `sm_86` | 444 | 0/2 | 0/2 |
| `sm_86` | 1900 | 0/2 | 0/2 |

Identical in every cell. Co-tenancy neither introduced divergence where there
was none nor suppressed it where there was. Notably the cross-architecture
difference reported in
[trap 94](94-temp0-reproducibility-is-architecture-dependent.md) survives
co-tenancy unchanged, which is part of why that result is stated as robustly as
it is.

## The one place a difference did show up

Median **prefill** throughput on the larger card fell from 3639.7 to 3348.7
tok/s, which is -8.0%, when the neighbour was active. The smaller card was flat:
3391.7 to 3367.0, which is -0.7%.

This is stated with its limits: **n=6, one prompt length, a single measurement
of each condition, and no repeat.** It is consistent with host-side or link
contention during prefill, which is the more host-bandwidth-sensitive phase, but
at that n we cannot separate an 8% effect from sampling noise. Recorded as a
lead, **not** as a result, and specifically not as "co-tenancy costs 8% of
prefill". If prefill latency matters to a reader, this is the cell to re-measure
with a proper n rather than the number to quote.

## Check it

Serve the same model twice, one process pinned per GPU with
`CUDA_VISIBLE_DEVICES`, confirm both have memory headroom, then run any
throughput or determinism probe twice, once with one lane idle and once with
both driven in parallel, and compare. Verify readiness with a completed
generation on each lane, not with an endpoint answering.

## Scope

Two consumer GPUs of different architectures in one host, two independent
llama.cpp processes, one build, one Mistral-family Q8_0 GGUF of unstated
provenance, both lanes with ample free VRAM. **This does not test the case
people usually mean by eviction**: two models on the *same* GPU competing for
one memory pool, or either lane running close to full. Both were deliberately
given headroom. A null here is not a null for those configurations. No claim
about Mistral checkpoints generally, about any named model, or about any
product.

**Related.** [Trap 81](../memory/81-stopped-container-has-not-released-memory.md)
is the sequential case, where a stopped lane has not yet released its device
memory, and is the one that does bite.

**Found.** 2026-07-28, first co-tenancy pass in this registry.

# Trap 94: temperature-0 reproducibility under concurrency holds on sm_86 and fails on sm_120, same binary, same weights

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28. One llama.cpp build,
`b9878-2da668617`, compiled for both architectures in a single binary
(`CMAKE_CUDA_ARCHITECTURES=86;120`), serving one Mistral-family Q8_0 GGUF of
unstated provenance, identical flags, on two GPUs in one host: `sm_120` (RTX
5090, compute capability 12.0) and `sm_86` (RTX 3090, compute capability 8.6).
Every request sends `cache_prompt: false`.

**Evidence pointer.** The same sweep script against two ports. The only variable
is `CUDA_VISIBLE_DEVICES`.

**Symptom.** A reproducibility guarantee validated on one machine does not hold
on another, and every obvious explanation is ruled out: same binary, same
weights, same flags, same host, same file.

## Why this exists

Almost every serving claim we hold is scoped to one GPU architecture, because
almost every claim was measured on one. Two cards of different generations in
one box, driven by one binary, is the cheapest way to find out whether that
scoping is a formality or a real limit. Here it is a real limit, and the
direction is the uncomfortable one: **the newer card is the one that loses a
guarantee the older card keeps.**

## Result

Concurrency 2 and 4, `cache_prompt: false`, pooled over two context settings
(`-c 131072` and `-c 32768`, which is 32768 and 8192 tokens per slot) and over
both co-tenancy states:

| prompt tokens | `sm_120` cells diverging | `sm_120` responses off | `sm_86` cells diverging | `sm_86` responses off |
|---|---|---|---|---|
| 108 to 136 | 0/16 | 0/128 | 0/16 | 0/128 |
| 220 | 11/16 | 33/128 | 14/16 | 41/128 |
| **444 to 1900** | **29/32** | **88/256** | **0/32** | **0/256** |

Concurrency-1 control, both cards, all lengths: 0/32 cells, 0/256 responses.

Read the three rows in order, because the middle one is what keeps this honest:

1. **Short prompts: both architectures deterministic.** No divergence anywhere.
2. **220 tokens: both architectures non-deterministic, at comparable rates.** If
   anything `sm_86` was slightly worse, 41 against 33 off-majority responses.
   **This is not "Ampere is reproducible and Blackwell is not."**
3. **444 tokens and above: the architectures separate completely.** `sm_120`
   diverged in 29 of 32 cells and 88 of 256 responses. `sm_86` diverged in
   **zero** of 32 cells and **zero** of 256 responses.

So the difference is not a global property of either card. It is a **regime**:
past a few hundred prompt tokens, the Ampere path returns to batch-invariant
reproducibility and the Blackwell path does not. We are reporting the boundary,
not a kernel-level mechanism for it; the plausible explanation is that the two
architectures select different attention or matmul paths at these shapes, with
different reduction orders, but we did not read kernel dispatch and do not claim
it.

## Confounds excluded

- **Memory pressure.** The first `sm_86` run left the card with 292 MiB free,
  which could plausibly have changed batch sizing. Repeating the whole
  comparison at `-c 32768`, where that card had 12610 MiB free, reproduced the
  identical pattern: `sm_86` 0/16 diverging cells at 444 or more tokens,
  `sm_120` 8/8.
- **Build skew.** One binary, one `system_fingerprint` (`b9878-2da668617`)
  confirmed from `/props` on both lanes. Not two builds.
- **Weights and flags.** Same file, same `-ngl 999 -c <n> -np 4 -fa on --jinja`.
- **Prompt cache.** Disabled per request on both.
- **A busy neighbour.** The pattern is unchanged with the other card idle or
  sweeping simultaneously: see
  [trap 95](95-two-gpu-co-tenancy-does-not-perturb-either-lane.md).

## What to do with it

- **A temperature-0 reproducibility guarantee validated on one GPU generation
  does not transfer to another, on the same binary and weights.** If
  reproducibility is a requirement, meaning exact-match scoring, cached answers,
  a regression suite pinning known-good output, or anything replaying a recorded
  trace, it has to be re-validated per architecture, at a realistic prompt
  length, at concurrency above 1.
- Concurrency 1 was reproducible in 512/512 responses on both cards.
  Serialising the lane remains the reliable lever where exactness actually
  matters.
- Do not generalise this to "newer GPUs are less deterministic". Two cards is
  two cards. What is established is that the axis exists and is worth a row in
  any claim table, not a ranking of vendors or generations.

## Check it

Serve the same file twice from one host, one process pinned per GPU with
`CUDA_VISIBLE_DEVICES`, same flags. Run the hash sweep from
[trap 91](91-concurrency-nondeterminism-has-a-prompt-length-floor.md) against
both ports at a prompt length above the floor, at concurrency 2, with
`cache_prompt: false`. Compare the distinct-hash counts per port, not the
answers.

## Scope

Two consumer GPUs, one host, one build (`b9878-2da668617`, arch `86;120`), one
Mistral-family Q8_0 GGUF of unstated provenance, `--jinja`. Counts and the
444-token boundary are measured here and should be re-measured, not assumed, on
other builds, other cards, and other files. No capability claims, no benchmark
of either card's quality, no claim about Mistral checkpoints generally, about
any named model, or about any product.

**Related.** [Trap 35](../evaluation/35-identical-weights-do-not-score-identically.md)
is the harness-level consequence: identical weights not scoring identically.
[Trap 91](91-concurrency-nondeterminism-has-a-prompt-length-floor.md) is the
effect this splits by architecture.

**Found.** 2026-07-28, first hardware-axis pass in this registry.

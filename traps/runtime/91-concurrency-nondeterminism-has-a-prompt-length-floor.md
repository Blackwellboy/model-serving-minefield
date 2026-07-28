# Trap 91: multi-slot continuous batching is non-deterministic at temperature 0, and the obvious minimal reproduction is too small to show it

**Found by Blackwellboy.** Target supplied by Exile.

**Status: reproduced here**, 2026-07-28, llama.cpp `b9878-2da668617` serving a
Mistral-family Q8_0 GGUF of unstated provenance, `--jinja`, `-np 4 -fa on`, on
two consumer GPUs. Cache-independent: every request below sends
`cache_prompt: false`.

**Evidence pointer.** Eight identical `temperature: 0`, fixed-`seed` requests
per cell on the reader's own lane, hashed and counted. No files from us needed.

**Symptom.** A lane is validated for reproducibility by sending the same
`temperature: 0` request several times, confirming byte-identical replies, and
shipping. Under real traffic the same request starts returning different
answers. The reproducibility check passed and was still wrong, because the
check used a short prompt and one request at a time.

## What actually governs it

Three conditions, and the claim as usually worded ("multi-slot output is
non-deterministic") names only one of them.

**1. Concurrency of at least 2 is necessary.** With `cache_prompt: false`, every
concurrency-1 cell in this study was byte-identical:

| arm | cells diverging | responses off majority |
|---|---|---|
| concurrency 1, all prompt lengths, both GPUs | 0/64 | 0/512 |

That is the negative control, and it is what makes the positive result below a
statement about batching rather than about the sampler or the seed.

**2. There is a prompt-length floor, and it is above the length of a natural
minimal reproduction.** Pooled over both GPUs, both context settings, and
concurrency 2 and 4:

| prompt tokens | cells diverging | responses off majority |
|---|---|---|
| 108 to 136 | 0/32 | 0/256 |
| 220 | 25/32 | 74/256 |
| 444 to 1900 | 29/64 | 88/512 |

A 108-token prompt never diverged, in 256 concurrent responses, at any
concurrency tested. A 220-token prompt diverged in 25 of 32 cells. **An
experimenter who writes the smallest prompt that exercises the bug they have in
mind will conclude the lane is deterministic, and will be wrong.** This is the
part worth carrying away: the failure mode of this reproduction is a false
negative, not a false positive.

**3. It is not monotone in concurrency.** Concurrency 2 diverged more reliably
than concurrency 4 in most cells: at 444 tokens on the Blackwell card, 8/8
replicates at concurrency 2 against 5/8 at concurrency 4. "Add more load to make
it worse" is not sound advice here; a ragged batch appears to matter more than a
full one. We are reporting the observation, not a mechanism for it.

## The divergence is semantic, not whitespace

Three variants seen in one 8-request cell, differing in the final clause:

```
... can be divided by 2, making them composite, not prime.
... can be divided by 2, making them non-prime.
... can be divided by 2, making them composite numbers, not primes.
```

All three are correct answers, which is exactly why this survives review: an
eyeball check of a sample passes, and only a hash comparison catches it. A
scorer keyed on exact match, a cached-answer layer, or a regression suite
pinning known-good output will all see intermittent failures with no bad output
to point at.

## Check it

Send N identical requests at concurrency 2 with a prompt of at least a few
hundred tokens, `temperature: 0`, a fixed `seed`, and `cache_prompt: false`, then
hash the completions:

```bash
# repeat 8x concurrently against the same lane
curl -s localhost:PORT/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "messages":[{"role":"user","content":"<PAD to >=220 tokens> List the first eight prime numbers, then explain in two sentences why two is the only even prime."}],
  "max_tokens":96, "temperature":0, "seed":1234, "cache_prompt":false}' \
| python3 -c 'import json,sys,hashlib; print(hashlib.sha256((json.load(sys.stdin)["choices"][0]["message"]["content"]).encode()).hexdigest()[:16])'
```

More than one distinct hash confirms it. `cache_prompt: false` matters: leave it
out and you are measuring a second, separate effect as well, which is
[trap 92](92-prompt-cache-is-a-second-divergence-source.md).

## Scope

llama.cpp `b9878-2da668617` with `-np 4 -fa on`, one Mistral-family Q8_0 GGUF of
unstated provenance. The mechanism is server-side and we expect it wherever
continuous batching changes reduction order, but the **length floor and the
concurrency shape are measured on this build and this file only**, and the floor
in particular should be re-measured rather than assumed. We make no claim about
Mistral checkpoints generally, about any named model, or about any product.

**A hardware caveat that matters for anyone reproducing this.** The long-prompt
result above is not architecture-independent: it holds on `sm_120` and does
**not** hold on `sm_86` on the same binary and the same weights. See
[trap 94](94-temp0-reproducibility-is-architecture-dependent.md). Reproducing
this on an Ampere card at 444 or more tokens will return a null.

**Related.** [Trap 92](92-prompt-cache-is-a-second-divergence-source.md) is the
other divergence source and must be switched off before this one can be
characterised. [Trap 88](88-cache-prompt-false-does-isolate-here.md) is why
`cache_prompt: false` can be trusted to do that on this build.

**Found.** 2026-07-28, second coverage pass on this file.

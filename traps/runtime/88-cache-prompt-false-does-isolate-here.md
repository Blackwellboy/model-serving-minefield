# Trap 88: on llama.cpp `b9878`, `cache_prompt: false` DOES isolate a request from prior slot state

**Found by Blackwellboy.** Target supplied by Exile.

**Status: measured here, raw not published**, 2026-07-28, llama.cpp `b9878-2da668617`, one
Mistral-family Q8_0 GGUF of unstated provenance, four slots, 10600-token shared
prefix, `temperature=0`. Raw not published.

**Why this is recorded.** Two prior data points on two other stacks reported
that `cache_prompt` does not isolate a request from prior slot state. This is a
third measurement on a third stack, and it does **not** reproduce that. A
negative belongs in the registry with the same care as a positive, and the
scope boundary is the useful part.

**Measured.** Five sequential requests sharing a 10600-token prefix, differing
only in a trailing instruction:

| # | `cache_prompt` | `cached_tokens` | `cache_n` |
|---|---|---|---|
| 1 | default (on) | 0 | 0 |
| 2 | default (on) | 10600 | 10600 |
| 3 | **false** | **0** | **0** |
| 4 | **false** | **0** | **0** |
| 5 | default (on) | 10600 | 10600 |

Two things hold here that the prior reports say did not hold elsewhere. Rows 3
and 4 are genuinely uncached, not merely reported as such. And row 5 shows the
cache was neither poisoned nor discarded by the two isolated requests in
between: the shared prefix was still there afterwards at full length.

**What this does and does not say.** It says the flag is honoured on this
build. It does not refute the prior findings on their stacks; isolation is a
per-implementation property and the sensible reading is that the claim needs a
build qualifier rather than being true or false in general. Anyone carrying the
"cache_prompt does not isolate" warning forward should name the stack it was
measured on.

**Check it.** Warm a long prefix, send the same prefix with `cache_prompt:
false`, and read the cached-token count in the usage block. Then send it once
more with the default and confirm the cache survived.

**Scope.** llama.cpp `b9878-2da668617` only. Server property. The served target
supplied the tokens and nothing else.

**Found.** 2026-07-28.

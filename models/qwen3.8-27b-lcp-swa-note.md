# Qwen3.8-27B — long-session LCP / hybrid-SWA reliability note

**Evidence status: first-party observed, not a canonical trap.**

This note records a September 2026 RTX 5090 serving incident and its production mitigation. It is intentionally narrower than a canonical Minefield entry because the failing arm is intermittent.

Tracking issue: [#125](https://github.com/Blackwellboy/model-serving-minefield/issues/125).

## Tested stack

- RTX 5090
- Qwen3.8-27B-OBLITERATED Q4_K_M
- TurboQuant llama.cpp `tqp-v0.3.0`, `b1-30d6881` family
- context 300032
- KV K=q8_0 / V=turbo4
- MTP draft n=2 unless noted
- reasoning medium

## Symptom

Long agent sessions occasionally entered a large semantic repetition loop while the endpoint remained healthy and generation continued normally at the transport level. MTP acceptance stayed high during failures (~0.925–0.994), so speculative acceptance was not a semantic-quality signal.

Disabling context checkpoints removed one earlier failure path but did **not** close the incident: two later production loops occurred with `ctx-checkpoints=0` and checkpoint restore absent.

## Matched discriminator

At roughly 45.5K prompt tokens:

| Arm | Result |
|---|---|
| `ctx-checkpoints=0`, default LCP/slot similarity, MTP n2 | FAIL in 1/2 matched runs; one failure repeated a semantic span ~68 times / ~20K output tokens |
| same config plus `--slot-prompt-similarity 0.0` | PASS 2/2; LCP selections=0 |
| `ctx-checkpoints=0`, default LCP, MTP off | FAIL; MTP was not required for the failure |

The LCP-off winner then passed real agent/tool recertification at approximately 45K, 64K, 90K and 128K with zero semantic loops, zero PEG-native failures and zero unbounded tool loops.

## Important boundary

Forced full prompt re-processing still occurred with LCP disabled: 56 logged events / `n_past=0`-class resets across the recertification. No semantic loop occurred.

Supported conclusion:

> On this tested Qwen3.8 hybrid/SWA serving path, LCP-selected prior slot state is a high-confidence trigger/participant in the semantic-loop failure. Forced full re-prefill alone is insufficient. The exact low-level state-corruption mechanism remains unproven.

## Production mitigation

```text
ctx-checkpoints=0
slot-prompt-similarity=0.0
MTP n=2
KV q8_0/turbo4
reasoning medium
```

The winner measured about 99.8 tok/s on the short decode check and passed the long Hermes recertification. Reliability was preferred over LCP reuse performance.

## Why this is not a trap number yet

The failing LCP-on arm reproduced in only one of two matched runs. The LCP-off arm stayed clean in two matched runs plus the full-depth recertification, which is enough to operate safely but not enough to generalize the mechanism to all llama.cpp hybrid/SWA models.

Promotion should wait for another matched A-fail/B-pass reproduction or upstream/source evidence identifying the invalid LCP-selected state transition.

Related material to compare before promotion:

- `runtime/47` — prefix caching auto-disabled on hybrid state
- `runtime/60` — cold prefill and cache-hit disagreement
- `runtime/88` — cache-prompt isolation behavior
- `runtime/92` — prompt cache as a second divergence source
- `runtime/122` — Qwen3.8 MTP verification corruption under full CUDA graph, a different discriminator
- `upstream/U13` — iSWA cache reuse requires the retained full state

A downstream observation was prepared for `ggml-org/llama.cpp#25592`, but the connected GitHub integration did not have permission to post it. Do not cite that upstream comment as sent.

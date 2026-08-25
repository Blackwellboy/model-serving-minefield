# SGLang v0.5.18 upstream promotion pass

**Date:** 2026-08-25

This is the promotion record for the `UPSTREAM_READY` subset of
[`2026-08-25-sglang-veloGB10-glm52-public-source-harvest.md`](2026-08-25-sglang-veloGB10-glm52-public-source-harvest.md).

**Canonical trap count impact: 0.** These are `upstream/` entries only. Nobody here has reproduced them, they do not enter Core, they do not count toward Doctor coverage, and they do not increment the 133-entry measured registry.

## Promotion map

| Harvest | Upstream entry | Primary source | Disposition |
|---|---|---|---|
| H25-01 | U27 | SGLang #34189 | promoted, distinct hard-coded DSV4 write-pad mechanism |
| H25-02 | U28 | SGLang #34184 | promoted, distinct stale captured track-row/prefix-cache mechanism |
| H25-03 | U29 | SGLang #33517 | promoted, distinct virtual-vs-physical KV-id mechanism |
| H25-04 | U30 | SGLang #33974 | promoted, recycled partial-page tail mechanism |
| H25-05 | U31 | SGLang #33974 | promoted separately, int32 slot-stride wrap mechanism |
| H25-06 | U32 | SGLang #33758 | promoted, stop/EOS vs length ordering under multi-token accept |
| H25-07 | U33 | SGLang #34524 | promoted, absent checkpoint metadata + runtime default drift |
| H25-08 | U34 | SGLang #33912 | promoted, DCP replication omitted from exact draft-KV accounting |
| H25-09 | U35 | SGLang #34372 | promoted, resolvable but incompatible Blackwell FA4 dependency pair |

## Duplicate boundaries checked

The candidates were compared against the current registry and upstream tier before promotion. Adjacent material remains adjacent rather than being rewritten:

- Trap 122 is a Qwen3.8/vLLM FULL-vs-PIECEWISE graph corruption mechanism; U27 and U28 are different SGLang state-write/captured-track mechanisms.
- Trap 28 and U16 cover speculative failures at concurrency/batch boundaries without these source-level mechanisms.
- Existing prefix-cache and memory traps do not encode U28's stale `mamba_track_*` destination rows, U30's recycled page-tail exposure, U31's int32 stride wrap, or U34's DCP draft-budget omission.
- Existing versioning/provenance material does not encode U33's missing `is_causal` semantic-default change or U35's dependency pair that resolves successfully but fails Blackwell compilation.

This pass therefore promotes the source-level mechanisms without changing or inflating the measured registry.

## Not promoted from the same harvest

The remaining SGLang release notes and the `glm52-spark-kit` / `veloGB10` findings stay in their original `EXISTING_EXTENSION`, `LEAD_QUEUE`, `CONTROL_ONLY`, or `NOT_TRAP` dispositions. Community-repo findings are not silently upgraded to upstream entries just because their engineering detail is strong.

No third-party issue was created and no upstream project was contacted during this pass.
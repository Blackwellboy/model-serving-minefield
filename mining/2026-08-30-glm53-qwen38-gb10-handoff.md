# Handoff: GLM-5.3 / Ling-3.0 / Qwen3.8 GB10 Minefield harvest

**Date:** 2026-08-30

This file is the durable resume point for the owner or another ChatGPT/Grok session.

## Repository state

- Repo: `Blackwellboy/model-serving-minefield`
- Branch: `mining/glm53-qwen38-gb10-harvest-20260830`
- Draft PR: `#79` - `Mining: harvest GLM-5.3, Ling-3.0 and Qwen3.8 GB10 serving leads`
- Base: `main`
- Canonical trap-count impact from this harvest: **0**; source-ready items promoted below went to the non-canonical `upstream/` tier, not `traps/`

## Durable artifacts

1. `mining/2026-08-30-glm53-qwen38-gb10-public-source-harvest.md`
   - 48 findings/controls/extensions, H30-01 through H30-48.
   - Six unique source repos pinned to exact revisions.
   - Source-vetting notes, contradictions, duplicate map, claim boundaries.
   - Original 14-item confirm/refute verification queue.
   - Explicit list of findings not to promote blindly.

2. `mining/2026-08-30-glm53-qwen38-gb10-tweet-bank.md`
   - Ready-to-edit public post draft for every H30-01 through H30-48 item.
   - Evidence language preserved: source-confirmed, community-only, open, extension, control, or retracted.
   - Suggested public posting order for the strongest findings.

3. `mining/2026-08-30-glm53-qwen38-gb10-adjudication-pass-1.md`
   - Reopened the primary public sources for H30-08 / 10 / 11 / 12.
   - Promoted source-ready records as U36-U39 without changing the canonical trap count.
   - Records exact dedupe boundaries against Trap 128, Trap 106, Trap 135 and U34.
   - H30-08 primary vLLM #54150 read is complete; loader root cause remains unresolved.

4. This handoff file.

## Source repositories mined

1. `tonyd2wild/GLM-5.3-DGX-Spark-Cookbook` @ `f72b0ddfd491c815027f9b56c82af4866f24e01b`
2. `tonyd2wild/GLM-5.3-Flash-NVFP4-1M-KV-4x-DGX-Spark` @ `1ffba70df364ed0f044b2aba4d99cf492e9ebf85`
3. `tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark` @ `1f03bab8744065d9c7ef3d8e1e6b21d2fea698dc`
4. `MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks` @ `79f10b91f84779b2b1ff2c9327b1a5847cd97f70`
5. `MiaAI-Lab/Ling-3.0-Flash-SGLang-DSpark-DGX-Spark` @ `ca840cb8d032353e24648aeee06312b0938348f6`
6. `MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks` @ `0f950012c8d8323acac9a08846a32ef7953f5f62`

## Adjudication completed in pass 1

- **H30-10 -> U36**: warm-restart `sitecustomize` stdout contaminates command-substituted JSON. Primary issue #15 read; fix commit `f68130a` and regression test inspected. Status upstream-reported, maintainer confirmed, closed/fixed.
- **H30-11 -> U37**: 100K cold-prefill decode starvation. Primary issue #6 and maintainer reproduction/fix read. Status upstream-reported, maintainer reproduced, closed/fixed. Kept distinct from Trap 128 because Trap 128 owns an inert admission flag; U37 owns a real mixed-step token-budget/sparse-prefill cost mechanism.
- **H30-12 -> U38**: DFlash BlockPool-ID capacity tax. Primary issue #13 + merged PR #14 read. Status upstream-reported, maintainer reproduced, closed/fixed. Kept distinct from Trap 106 leak-diagnosis, Trap 135 execution-concurrency and U34 DCP-factor undercount.
- **H30-08 -> U39**: ModelOpt NVFP4 invalid byte-token sequences on SM120. Primary vLLM #54150 and its cross-reference comment read. Status upstream-reported, maintainer engagement none, issue open. The behavior is recorded; damaged conversion versus vLLM ModelOpt-loader cause is explicitly unresolved.

None of U36-U39 is a first-party Blackwellboy reproduction and none counts toward the canonical trap total.

## Strongest remaining promotion candidates

- H30-01 explicit KV pin bypassing activation reserve
- H30-03 GB10 UVM livelock / high-util low-power no-progress state
- H30-05 dependency-induced NCCL downgrade breaking fabric
- H30-07 uninitialized but in-range sparse-indexer pool IDs
- H30-09 padded/strided KV view causing allocator blow-up
- H30-15 Qwen3.8 MTP positional/LSE/master-slice doom-loop mechanisms
- H30-16 heterogeneous cache groups requiring different dtype contracts
- H30-19 production-state-dependent blank tool args; unresolved, do not blame DFlash/parser yet
- H30-22 speculative grammar-state transition inside draft window
- H30-24 generic grouped-KV allocator mismatch
- H30-43 shared `/dev/shm` CUDA-IPC collision
- H30-44 media-preprocessor frame-estimator OOM

## Critical claim boundaries

- The mining packet is public-source research, **not first-party Blackwellboy reproduction**.
- Do not convert all 48 items into numbered canonical traps. Several are existing extensions, controls, open questions, or source-vetting lessons.
- U36-U39 are the weaker upstream tier and must never be described as reproduced here.
- H30-31 / Mia GLM issue #24 is **not a bug candidate**. The reporter explicitly withdrew confidence. Preserve it as source-vetting evidence.
- Ling `thinking:false` is already Trap 126.
- Qwen full-CUDA-graph MTP corruption is already Trap 122.
- Qwen hard-coded RDMA GID is Trap 114 territory.
- Shared JIT cache is existing U19 territory.
- Workload-dependent speculative acceptance belongs to Trap 111 family.

## Remaining verification queue

1. H30-01 explicit KV pin / activation reserve A/B.
2. H30-03 capture a naturally occurring UVM livelock; do not deliberately OOM a production Spark.
3. H30-05 reproduce dependency-induced NCCL downgrade in a disposable environment.
4. H30-07 source-level poison/sentinel test for uninitialized pool IDs.
5. H30-09 read/verify the exact padded/strided allocation path and allocator request.
6. H30-15 split Qwen MTP shift/LSE/slice into one-variable tests.
7. H30-16 prove effective dtype per cache group.
8. H30-19 require raw XML/token IDs + finish/timeout/cache state from a failing production turn.
9. H30-22 primary runtime patch read, then construct a draft window crossing the state transition.
10. H30-24 code-level dedupe against U38 before any separate promotion.
11. H30-43 shared vs private `/dev/shm` CUDA-IPC A/B.
12. H30-44 bounded media-preprocessor frame-estimator test.
13. U39 follow-up only when vLLM #54150 gains maintainer/fix evidence or a conversion-vs-loader control localizes cause.

## Existing commits from the original harvest

- `9aaa53d157a79a4f3a22e9f6fb0b5f8544048238` - initial 48-item public-source harvest packet.
- `f92f4d2d773000a280cd65665d4c4c2867bce776` - complete H30-01 through H30-48 tweet bank.
- `f455068d746400f2a31f7acaf314ec628174f1f8` - original durable handoff.

Later commits on this same branch add U36-U39, update `upstream/README.md`, add adjudication pass 1, and refresh this handoff. Use PR #79 head as current truth rather than the original handoff SHA.

## Resume instruction

Read this file first, then `mining/2026-08-30-glm53-qwen38-gb10-adjudication-pass-1.md`, then the full harvest packet and tweet bank as needed. Do not reconstruct H30 state from chat memory. Before promoting another candidate, run the packet's duplicate/mechanism check against current `traps/`, `upstream/`, `leads/` and `mining/OPEN_QUESTIONS.md`, reopen the primary source, and preserve the source status vocabulary.

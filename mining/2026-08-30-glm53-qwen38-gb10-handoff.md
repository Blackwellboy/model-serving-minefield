# Handoff: GLM-5.3 / Ling-3.0 / Qwen3.8 GB10 Minefield harvest

**Date:** 2026-08-30

This file is the durable resume point for the owner or another ChatGPT/Grok session.

## Repository state

- Repo: `Blackwellboy/model-serving-minefield`
- Branch: `mining/glm53-qwen38-gb10-harvest-20260830`
- Draft PR: `#79` - `Mining: harvest GLM-5.3, Ling-3.0 and Qwen3.8 GB10 serving leads`
- Base: `main`
- Canonical trap-count impact from this harvest: **0**; promoted items below live only in the non-canonical `upstream/` tier

## Durable artifacts

1. `mining/2026-08-30-glm53-qwen38-gb10-public-source-harvest.md`
   - 48 findings/controls/extensions, H30-01 through H30-48.
   - Six source repos pinned to exact revisions.
   - Source-vetting notes, contradictions, duplicate map and confirm/refute queue.

2. `mining/2026-08-30-glm53-qwen38-gb10-tweet-bank.md`
   - Draft public post for every H30 item with its original evidence status preserved.

3. `mining/2026-08-30-glm53-qwen38-gb10-adjudication-pass-1.md`
   - H30-08 / 10 / 11 / 12 primary-source adjudication.
   - Promotions U36-U39.

4. `mining/2026-08-30-glm53-qwen38-gb10-adjudication-pass-2.md`
   - H30-22 split into two source-exact vLLM mechanisms.
   - Promotions U40-U41.

5. `mining/2026-08-30-glm53-qwen38-gb10-adjudication-pass-3.md`
   - H30-19 primary issue + maintainer negative-control review.
   - Promotion U42 as unresolved/open, not as a DFlash/parser cause claim.

6. This handoff file.

## Source repositories mined

1. `tonyd2wild/GLM-5.3-DGX-Spark-Cookbook` @ `f72b0ddfd491c815027f9b56c82af4866f24e01b`
2. `tonyd2wild/GLM-5.3-Flash-NVFP4-1M-KV-4x-DGX-Spark` @ `1ffba70df364ed0f044b2aba4d99cf492e9ebf85`
3. `tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark` @ `1f03bab8744065d9c7ef3d8e1e6b21d2fea698dc`
4. `MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks` @ `79f10b91f84779b2b1ff2c9327b1a5847cd97f70`
5. `MiaAI-Lab/Ling-3.0-Flash-SGLang-DSpark-DGX-Spark` @ `ca840cb8d032353e24648aeee06312b0938348f6`
6. `MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks` @ `0f950012c8d8323acac9a08846a32ef7953f5f62`

## Adjudication completed

- **H30-10 -> U36**: warm-restart `sitecustomize` stdout contaminates command-substituted JSON. Mia issue #15 + fix commit `f68130a` + regression test inspected. Upstream-reported, maintainer confirmed, closed/fixed.
- **H30-11 -> U37**: long cold prefill starves peer decode without preemption. Mia issue #6 + maintainer reproduction + fix commit `f3043c9` inspected. Upstream-reported, maintainer reproduced, closed/fixed. Distinct from Trap 128's inert admission flag.
- **H30-12 -> U38**: DFlash standalone BlockPool-ID tax makes global KV-token capacity non-fungible. Mia issue #13 + merged PR #14 inspected. Upstream-reported, maintainer reproduced, closed/fixed. Distinct from Trap 106, Trap 135 and U34.
- **H30-08 -> U39**: ModelOpt NVFP4 invalid byte-token sequences on SM120. vLLM #54150 read. Upstream-reported, no maintainer engagement, open. Damaged conversion versus loader path remains unresolved.
- **H30-22a -> U40**: XGrammar speculative token batches can keep advancing after the matcher terminates. vLLM issue #52767 + merged PR #52805 inspected. Upstream-reported, maintainer confirmed, closed/fixed.
- **H30-22b -> U41**: grammar can activate at reasoning-end inside a speculative window, so pre-transition draft tokens must be validated before advance. Merged vLLM PR #53046 inspected. Upstream-reported, maintainer confirmed, closed/fixed.
- **H30-19 -> U42**: blank/missing required tool args reported only under production-like state. Mia issue #10 + maintainer investigation read. Upstream-reported, maintainer responded, open. Mia's 53-case synthetic was clean and global glm47 parser-state leak was ruled out; no DFlash/prefix-cache/batching/parser root cause is claimed.

None of U36-U42 is a first-party Blackwellboy reproduction and none counts toward the canonical trap total.

## Strongest remaining promotion / verification candidates

- H30-01 explicit KV pin bypassing activation reserve
- H30-03 GB10 UVM livelock / high-util low-power no-progress state
- H30-05 dependency-induced NCCL downgrade breaking fabric
- H30-07 uninitialized but in-range sparse-indexer pool IDs
- H30-09 padded/strided KV view causing allocator blow-up
- H30-15 Qwen3.8 MTP positional/LSE/master-slice doom-loop mechanisms
- H30-16 heterogeneous cache groups requiring different dtype contracts
- H30-24 generic grouped-KV allocator mismatch; exact dedupe against U38 still required
- H30-43 shared `/dev/shm` CUDA-IPC collision
- H30-44 media-preprocessor frame-estimator OOM

## Source review completed but not promoted

- **H30-05**: Tony's pinned deploy report directly records FlashInfer nightly changing NCCL 2.30.7 -> 2.29.7 followed by `ncclCommInitRank` failure and recovery after restoring 2.30.7. It remains mining/verification rather than `upstream/` because the current upstream-tier integrity contract requires a tracker/PR lifecycle and no matching primary issue/PR was found in the source repo.
- **H30-09 / H30-24 source evidence**: Tony's pinned DFlash2 document directly records the generic uniform-page failure family, including an LCM path inflating one request to ~27.92 GiB and a padded strided view requesting ~13.59 GB from a ~377 MB tensor. This is strong public source evidence but remains mining pending exact owner/dedupe and a suitable primary tracker/fix lifecycle.
- **H30-07**: the Tony deploy report contains the `torch.empty` -> initialized/sentinel indexer hardening claim, but the two upstream issues it cites as related classes are not the same mechanism on inspection. Do not launder those issue numbers into confirmation of H30-07.

## Critical claim boundaries

- Do not convert all H30 items into canonical traps.
- `upstream/` is intentionally weaker than `traps/`; U36-U42 must never be described as reproduced here.
- H30-31 / Mia issue #24 remains a source-vetting lesson, not a bug candidate; its reporter withdrew confidence.
- Ling `thinking:false` is already Trap 126.
- Qwen full-CUDA-graph MTP corruption is already Trap 122.
- Qwen hard-coded RDMA GID is Trap 114 territory.
- Shared JIT cache is U19.
- Workload-dependent speculative acceptance is Trap 111 family.
- U32 is SGLang EOS/stop plus output-length-cap ordering; it is not the owner of U40 or U41.

## Remaining verification queue

1. H30-01 explicit KV pin / activation reserve A/B.
2. H30-03 capture a naturally occurring UVM livelock; do not deliberately OOM production hardware.
3. H30-05 reproduce dependency-induced NCCL downgrade in a disposable environment.
4. H30-07 source-level poison/sentinel test for uninitialized pool IDs.
5. H30-09 exact allocator/storage-span reproduction or primary fix trail.
6. H30-15 split Qwen MTP shift/LSE/slice into one-variable tests.
7. H30-16 prove effective dtype per cache group.
8. H30-24 code-level dedupe against U38 before any separate promotion.
9. H30-43 shared vs private `/dev/shm` CUDA-IPC A/B.
10. H30-44 bounded media-preprocessor frame-estimator test.
11. U39 follow-up only when vLLM #54150 gains maintainer/fix evidence or a conversion-vs-loader control localizes cause.
12. U42 follow-up only when a failing raw production artifact captures generated tokens/XML plus finish/timeout/cache state.

## Original harvest commits

- `9aaa53d157a79a4f3a22e9f6fb0b5f8544048238` - 48-item public-source harvest.
- `f92f4d2d773000a280cd65665d4c4c2867bce776` - H30-01 through H30-48 tweet bank.
- `f455068d746400f2a31f7acaf314ec628174f1f8` - original handoff.

Use PR #79 head as current truth; later commits add U36-U42, source adjudication passes, the updated upstream index and this refreshed handoff.

## Resume instruction

Read this file first, then adjudication passes 1-3, then the full harvest packet/tweet bank as needed. Before any further promotion, dedupe against current `traps/`, `upstream/`, `leads/` and `mining/OPEN_QUESTIONS.md`, reopen the primary source, and preserve the source-status vocabulary.

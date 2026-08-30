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

6. `mining/2026-08-30-reederey87-glm53-exl3-2x-dgx-spark-harvest.md`
   - Reederey87 production-kit deep review, R87-01 through R87-21.
   - Source pinned at `936661ec4af7abfee89247a253709223af64a07c`.
   - Strong new leads: persistent JIT shape contamination, hybrid KDA page-boundary cache veto, dense-retention multi-session collapse, long-prefill HOL, Mamba resume wrong-block-size crash, stale/effective config logging, router-numerics/spec-acceptance coupling, cache metric semantics, source-vs-prebuilt rebuild drift, speculation changing cache geometry, GB10 UMA sysctl parity, and path-scoped API auth.
   - vLLM #54199 explicitly preserved as RETRACTED/duplicate of #53142, not a separate bug.

7. This handoff file.

## Source repositories mined

1. `tonyd2wild/GLM-5.3-DGX-Spark-Cookbook` @ `f72b0ddfd491c815027f9b56c82af4866f24e01b`
2. `tonyd2wild/GLM-5.3-Flash-NVFP4-1M-KV-4x-DGX-Spark` @ `1ffba70df364ed0f044b2aba4d99cf492e9ebf85`
3. `tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark` @ `1f03bab8744065d9c7ef3d8e1e6b21d2fea698dc`
4. `MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks` @ `79f10b91f84779b2b1ff2c9327b1a5847cd97f70`
5. `MiaAI-Lab/Ling-3.0-Flash-SGLang-DSpark-DGX-Spark` @ `ca840cb8d032353e24648aeee06312b0938348f6`
6. `MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks` @ `0f950012c8d8323acac9a08846a32ef7953f5f62`
7. `Reederey87/glm53-flash-exl3-2x-dgx-spark` @ `936661ec4af7abfee89247a253709223af64a07c`

## Adjudication completed

- **H30-10 -> U36**: warm-restart `sitecustomize` stdout contaminates command-substituted JSON. Mia issue #15 + fix commit `f68130a` + regression test inspected. Upstream-reported, maintainer confirmed, closed/fixed.
- **H30-11 -> U37**: long cold prefill starves peer decode without preemption. Mia issue #6 + maintainer reproduction + fix commit `f3043c9` inspected. Upstream-reported, maintainer reproduced, closed/fixed. Distinct from Trap 128's inert admission flag.
- **H30-12 -> U38**: DFlash standalone BlockPool-ID tax makes global KV-token capacity non-fungible. Mia issue #13 + merged PR #14 inspected. Upstream-reported, maintainer reproduced, closed/fixed. Distinct from Trap 106, Trap 135 and U34.
- **H30-08 -> U39**: ModelOpt NVFP4 invalid byte-token sequences on SM120. vLLM #54150 read. Upstream-reported, no maintainer engagement, open. Damaged conversion versus loader path remains unresolved.
- **H30-22a -> U40**: XGrammar speculative token batches can keep advancing after the matcher terminates. vLLM issue #52767 + merged PR #52805 inspected. Upstream-reported, maintainer confirmed, closed/fixed.
- **H30-22b -> U41**: grammar can activate at reasoning-end inside a speculative window, so pre-transition draft tokens must be validated before advance. Merged vLLM PR #53046 inspected. Upstream-reported, maintainer confirmed, closed/fixed.
- **H30-19 -> U42**: blank/missing required tool args reported only under production-like state. Mia issue #10 + maintainer investigation read. Upstream-reported, maintainer responded, open. Mia's 53-case synthetic was clean and global glm47 parser-state leak was ruled out; no DFlash/prefix-cache/batching/parser root cause is claimed.

None of U36-U42 is a first-party Blackwellboy reproduction and none counts toward the canonical trap total.

## Reederey87 addendum — strongest new queue

- **R87-01**: k=7→5→7 speculative A/B returned to the same config but persistent Triton/TileLang JIT products left structured acceptance ~0.58 versus ~0.96 until both nodes' caches were wiped. Potential distinct owner from U19 because no shared-cache/concurrent-build mechanism is required.
- **R87-02**: hybrid KDA recurrent state checkpoints only at the 3584-token page boundary; off-boundary chunking can make one KDA-group miss veto every attention cache hit and silently read ~0%.
- **R87-03**: dense KDA retention produced exact 0% cross-session reuse while solo 110k stayed ~98%; sparse retention restored 2×68k to 97.8% and 4×60k to 95%.
- **R87-04**: ~240k cold prefill caused a ~1.2k peer request to wait 256 s for first token; long-prefill threshold reduced it to 7.9 s for ~5% solo-prefill cost.
- **R87-05**: vLLM #53142 — hybrid Mamba prefix-cache resume uses the wrong block-size divisor; first/cold request passes, cached second request can seed state hundreds of columns out of range and IMA. Strong primary upstream candidate.
- **R87-06 / R87-19**: vLLM #54199's “equal block sizes” premise was retracted. The log printed a value before later code overwrote the effective block size; its crash is #53142, not a second bug.
- **R87-07**: merged vLLM #54048 legitimately improves GB10 router-GEMM precision, but Reederey87's DSv4 DSpark deployment measured acceptance 0.638→0.574/0.574 while ordinary correctness gates stayed green. Do not transfer that numeric result to GLM-5.3; W9 in the Reederey GLM repo needs its own acceptance A/B.
- **R87-08**: community measurement says global prefix-cache counters over-count 1.3–2× under queue pressure versus per-request `cached_tokens`; cited RFC #37003 does not itself prove that metric bug. Primary source still required.
- **R87-09**: `kv_cache_usage_perc` may read 0 at idle despite a warm reusable cache because it counts running-request blocks, not reusable cached blocks. Strong observability lead.
- **R87-10**: after explicit KV-byte pinning, `gpu_memory_utilization` sizes nothing but still gates boot on device `MemFree`, making page-cache state capable of moving a supposedly fixed boot over/under the threshold.
- **R87-11**: omitting async does not mean off; tri-state resolves enabled. Exact fork-specific 17.51-GiB admission result remains community measurement pending primary code-path pinning.
- **R87-12**: existing pinned image continued serving while the clean Docker build path was broken because a Dockerfile-referenced overlay had been deleted but remained baked into the image. Strong H30-32 source-reproducibility extension.
- **R87-13**: toggling speculation can also change derived hybrid block/page geometry, so a “spec A/B” can silently move cache geometry as a second variable.
- **R87-14**: `vm.min_free_kbytes` parity on GB10 UMA can affect GPU-visible memory per node; asymmetric sysctl state can masquerade as per-rank GPU-memory differences.
- **R87-21**: bearer auth is path-scoped, not necessarily server-global; root utility/reset routes can sit outside the guarded prefixes. Re-audit current upstream middleware before canonical promotion.

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
- R87-01 persistent shape-JIT A→B→A contamination
- R87-02 hybrid page-boundary cache veto
- R87-03 dense-vs-sparse recurrent-state retention collapse
- R87-05 wrong block-size divisor on hybrid cached resume
- R87-09 warm-cache invisible to idle KV-usage gauge
- R87-10 pinned-KV / boot-gate split behavior
- R87-13 speculation A/B changing cache geometry
- R87-21 path-scoped API auth surface

## Source review completed but not promoted

- **H30-05**: Tony's pinned deploy report directly records FlashInfer nightly changing NCCL 2.30.7 -> 2.29.7 followed by `ncclCommInitRank` failure and recovery after restoring 2.30.7. It remains mining/verification rather than `upstream/` because the current upstream-tier integrity contract requires a tracker/PR lifecycle and no matching primary issue/PR was found in the source repo.
- **H30-09 / H30-24 source evidence**: Tony's pinned DFlash2 document directly records the generic uniform-page failure family, including an LCM path inflating one request to ~27.92 GiB and a padded strided view requesting ~13.59 GB from a ~377 MB tensor. This is strong public source evidence but remains mining pending exact owner/dedupe and a suitable primary tracker/fix lifecycle.
- **H30-07**: the Tony deploy report contains the `torch.empty` -> initialized/sentinel indexer hardening claim, but the two upstream issues it cites as related classes are not the same mechanism on inspection. Do not launder those issue numbers into confirmation of H30-07.
- **R87-08**: keep as community-measured until the exact counter implementation/primary issue substantiates the 1.3–2× queue-pressure inflation claim; RFC #37003 is retention-policy context, not proof of that metric defect.
- **R87-11**: vLLM #47728 establishes async settled-vs-scheduled accounting bugs and a wider admission bound, but does not alone prove this fork's exact 17.51-GiB startup calculation.
- **R87-19**: #54199 is retracted and must never be minted separately; use #53142 for the actual block-size resume mechanism.

## Critical claim boundaries

- Do not convert all H30/R87 items into canonical traps.
- `upstream/` is intentionally weaker than `traps/`; U36-U42 must never be described as reproduced here.
- H30-31 / Mia issue #24 remains a source-vetting lesson, not a bug candidate; its reporter withdrew confidence.
- Ling `thinking:false` is already Trap 126.
- Qwen full-CUDA-graph MTP corruption is already Trap 122.
- Qwen hard-coded RDMA GID is Trap 114 territory.
- Shared multi-node JIT build-product corruption is U19; R87-01 may be distinct but must be deduped on cache-key mechanism.
- Workload-dependent speculative acceptance is Trap 111 family; R87-07 is potentially a stronger target-numerics/drafter-agreement specialization.
- U32 is SGLang EOS/stop plus output-length-cap ordering; it is not the owner of U40 or U41.

## Remaining verification queue

1. R87-05 source-adjudicate vLLM #53142 and related fixes for upstream tier.
2. R87-01 reproduce shape A→B→A with persistent caches, then wipe only compiled caches.
3. R87-02 inspect #42317/#45238 plus coordinator code for exact hybrid page-boundary veto ownership.
4. R87-03 reconcile sparse-retention behavior with current vLLM #52216 semantics and re-test cross-session shapes.
5. R87-09 verify `kv_cache_usage_perc` semantics in current source and make a warm-idle control.
6. R87-10 pin-vs-utilization-gate disposable GB10 boot A/B.
7. R87-13 record effective cache/page geometry in matched spec on/off A/B.
8. R87-21 inspect current auth middleware route prefixes, no GPU required.
9. R87-07 run GLM-5.3 W9 router-GEMM on/off with DFlash acceptance/per-position metrics; do not import DSv4's -10% number.
10. H30-01 explicit KV pin / activation reserve A/B.
11. H30-03 capture a naturally occurring UVM livelock; do not deliberately OOM production hardware.
12. H30-05 reproduce dependency-induced NCCL downgrade in a disposable environment.
13. H30-07 source-level poison/sentinel test for uninitialized pool IDs.
14. H30-09 exact allocator/storage-span reproduction or primary fix trail.
15. H30-15 split Qwen MTP shift/LSE/slice into one-variable tests.
16. H30-16 prove effective dtype per cache group.
17. H30-24 code-level dedupe against U38 before any separate promotion.
18. H30-43 shared vs private `/dev/shm` CUDA-IPC A/B.
19. H30-44 bounded media-preprocessor frame-estimator test.
20. U39 follow-up only when vLLM #54150 gains maintainer/fix evidence or a conversion-vs-loader control localizes cause.
21. U42 follow-up only when a failing raw production artifact captures generated tokens/XML plus finish/timeout/cache state.

## Original harvest commits

- `9aaa53d157a79a4f3a22e9f6fb0b5f8544048238` - 48-item public-source harvest.
- `f92f4d2d773000a280cd65665d4c4c2867bce776` - H30-01 through H30-48 tweet bank.
- `f455068d746400f2a31f7acaf314ec628174f1f8` - original handoff.
- `6b2e061379665f55386dec6e109fc48940423bea` - Reederey87 GLM-5.3 EXL3 production-kit mining addendum.

Use PR #79 head as current truth; later commits add U36-U42, source adjudication passes, the Reederey87 addendum, updated upstream index and this refreshed handoff.

## Resume instruction

Read this file first, then `mining/2026-08-30-reederey87-glm53-exl3-2x-dgx-spark-harvest.md`, adjudication passes 1-3, then the full H30 harvest packet/tweet bank as needed. Before any further promotion, dedupe against current `traps/`, `upstream/`, `leads/` and `mining/OPEN_QUESTIONS.md`, reopen the primary source, and preserve the source-status vocabulary.
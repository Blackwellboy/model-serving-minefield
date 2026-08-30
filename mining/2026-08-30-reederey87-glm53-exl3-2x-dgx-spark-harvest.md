# Public-source harvest addendum: Reederey87 GLM-5.3 EXL3 2x DGX Spark

**Date read:** 2026-08-30

**Source:** `Reederey87/glm53-flash-exl3-2x-dgx-spark`

**Pinned source head read:** `936661ec4af7abfee89247a253709223af64a07c`

**Canonical trap-count impact: 0.** This is a source-mining/adjudication addendum. It does not claim first-party Blackwellboy reproduction and reserves no canonical trap numbers.

The repo is unusually valuable for Minefield because it documents a live production deployment and keeps failed/reverted experiments, restart mechanics, cache geometry, and source-upgrade hazards rather than only publishing the final working command.

## Highest-value findings

| ID | Priority | Disposition | Short description |
|---|---|---|---|
| R87-01 | A+ | LEAD_QUEUE_HIGH | A k=7→5→7 speculative A/B returned to the same config but stale persistent JIT products left acceptance at 0.58 vs 0.96 until both nodes' caches were wiped |
| R87-02 | A+ | LEAD_QUEUE_HIGH | Hybrid KDA prefix caching silently reads 0% when scheduler chunks do not end on the recurrent-state page boundary; one missing KDA checkpoint vetoes every attention-group hit |
| R87-03 | A+ | LEAD_QUEUE_HIGH | Dense recurrent-state retention made multi-session prefix caching collapse to exact 0% while solo replay stayed ~98%; sparse retention restored 97.8% / 95% |
| R87-04 | A | LEAD_QUEUE_HIGH | A 240k cold prefill caused a 1.2k peer request to wait 256 s for first token; a long-prefill threshold cut it to 7.9 s for ~5% solo-prefill cost |
| R87-05 | A+ | PRIMARY_UPSTREAM_LEAD | Hybrid Mamba prefix-cache resume can divide by the wrong block size and seed a state column hundreds of entries out of range; first request passes, second cached request crashes |
| R87-06 | A | LEAD_QUEUE | The startup log can print the old/effective-at-that-moment block size before a later stage overwrites it; trusting the log produced the false premise of retracted vLLM #54199 |
| R87-07 | A+ | UPSTREAM/DEPLOYMENT_INTERACTION | A numerically more precise router-GEMM path was merged upstream for family-120, but a measured DSv4 speculative deployment lost ~10% draft acceptance while all ordinary correctness gates stayed green |
| R87-08 | A | LEAD_QUEUE / SOURCE_CHECK_REQUIRED | Repo reports global prefix-cache hit/query counters over-counting 1.3–2x under queue pressure versus per-request `cached_tokens`; cited RFC #37003 does not itself establish that exact counter bug |
| R87-09 | A | LEAD_QUEUE | `kv_cache_usage_perc` is 0 at idle even with a reusable warm cache because it counts blocks held by RUNNING requests; page accounting also overstates token-equivalent occupancy |
| R87-10 | A | LEAD_QUEUE | With explicit KV bytes pinned, `gpu_memory_utilization` sizes nothing but still acts as a boot gate using device `MemFree`; page cache can therefore make an otherwise identical boot crash-loop |
| R87-11 | A | LEAD_QUEUE / SOURCE_CHECK_REQUIRED | Omitting the async flag resolves to async ENABLED; on this hybrid geometry the resulting admission accounting refuses a serve that fits when async is explicitly off |
| R87-12 | A+ | LEAD_QUEUE_HIGH / H30-32 EXTENSION | The pinned prebuilt image continued to boot while the repository's clean BUILD path was broken because a Dockerfile-referenced overlay had been deleted but remained baked into the existing image |
| R87-13 | A | LEAD_QUEUE | Turning speculative decoding on/off changes derived hybrid block geometry (reported MTP k=2→1600, no-spec→800), so a “speculation A/B” can silently change the cache geometry too |
| R87-14 | A | LEAD_QUEUE | GB10 `vm.min_free_kbytes` reserves unified memory visible to the GPU; node asymmetry can present as phantom per-rank GPU-memory startup failure on otherwise matched Sparks |
| R87-15 | B+ | EXISTING_EXTENSION | `/health` can stay HTTP 200 through a stuck NCCL collective; use forward-progress checks. Trap 112 owner. |
| R87-16 | B+ | EXISTING_EXTENSION | systemd failed-start cleanup can leave wreckage holding ports while retries fail `check_port_free`; Trap 53/readiness-lifecycle family |
| R87-17 | B+ | EXISTING_EXTENSION | benchmarking after `/health` but before post-ready warmup completes contaminates throughput and spec counters; Trap 54 / 112 measurement ladder |
| R87-18 | B+ | EXISTING_EXTENSION | Static DFlash k=8 improved structured throughput ~2.5–3% but made prose ~9.1% worse because the extra draft slot was mostly rejected; Trap 111 workload-dependence evidence |
| R87-19 | B+ | SOURCE_VETTING | vLLM #54199 was explicitly retracted; its crash was real but belonged to #53142. The repo still cites #54199 as a caution, so issue lifecycle must be re-read at publication time |
| R87-20 | B+ | EXISTING_EXTENSION / MEASUREMENT | First post-restart passes reportedly read ~17% low on prose from parked-swap fault-in; run-order/warm-state extension rather than a model-speed claim |
| R87-21 | A | LEAD_QUEUE / SECURITY-SURFACE | `VLLM_API_KEY` guards selected route prefixes, while root-mounted `/tokenize`, `/detokenize`, and the locally exposed cache-reset route are outside that prefix set |

---

## R87-01 — returning the config does not return the compiled state

**Source:** `docs/03-bringup.md`.

A speculative A/B changed k=7 → 5 → 7. Even after returning to the original k=7 configuration, structured acceptance did **not** return to baseline: the repo reports roughly **0.96 → 0.58** until persistent Triton/TileLang JIT caches were wiped on **both** nodes. The production launcher now hashes shape-affecting config and invalidates those caches when the hash changes.

**Minefield owner candidate:** “same config after an A/B is not the same runtime state when compiled artifacts survive the arm.”

**Dedupe:** U19 is shared multi-node JIT cache corruption while generating build products. This report does not require a shared cache or concurrent compilation; it is persistent node-local cache contamination across sequential shape changes. Keep separate unless source inspection proves the same underlying cache-key defect.

**CONFIRM:** reproduce k=A→B→A with persistent caches; require A2 acceptance/output to differ from A1, then recover by wiping only the compiled caches with all model/runtime/request variables fixed.

## R87-02 — one recurrent-state cache miss can veto all attention cache hits

**Source:** `docs/04-prefix-caching.md`, `docs/02-parameters.md`.

GLM-5.3-Flash's hybrid KDA layers checkpoint recurrent state on a **3584-token page boundary** in align mode. The coordinator requires every cache group to hit. If a scheduler prefill step ends off-boundary, the KDA checkpoint is absent and vetoes attention-layer hits that otherwise exist. At MNBT=1024 the result was near/exact **0% cache hits with no useful log message**; at MNBT=3584 the page boundary is aligned.

**Portable lesson:** hybrid prefix-cache hit rate can be controlled by scheduler chunk geometry, not merely whether the prefix exists in attention KV.

**Dedupe:** related to Trap 60/92 cache-path measurement, but neither owns scheduler/page alignment causing a recurrent-state group to veto all cache groups.

## R87-03 — cache works solo, collapses under multi-session retention economics

**Source:** `docs/04-prefix-caching.md`, `docs/05-known-issues.md`.

Measured source rows:

- 2×68k sessions: dense retention **0.0%** cross-session hits → sparse retention (`VLLM_PREFIX_CACHE_RETENTION_INTERVAL=0`) **97.8%**.
- 4×60k concurrent ×3: **0%** → **95.0%**.
- Solo 110k: **98% → 98%** (held).

The source's final diagnosis is not a scheduler insertion bug: dense recurrent-state retention made cached pages too expensive to coexist. Sparse retention preserves replay boundaries while allowing sessions to share the pool.

**Minefield shape:** a sequential cache smoke test can be perfect while the production multi-session shape gives zero benefit.

## R87-04 — long-prefill head-of-line blocking can hide behind healthy decode

**Source:** `docs/06-improvement-plan.md`, commit `5a5b4a7ab650495cc170d2f1ba7705b99c0349fe`.

A ~1.2k request landing while a ~240k cold prefill was running waited **256 s** for first token. `LONG_PREFILL_TOKEN_THRESHOLD=1792` reduced that to **7.9 s**, trading about **5.1%** solo cold-prefill throughput (941→893 tok/s). Decode and cache retention were reported unchanged.

**Dedupe:** U37/H30-11 is a peer *decode* collapsing while a long prefill consumes the global engine step. R87-04 is short-request TTFT/HOL behind a long prefill and uses a threshold to preserve peer scheduling budget. They are adjacent scheduler economics, not automatically one mechanism.

## R87-05 / R87-06 — the printed block size can be stale, then prefix-cache resume uses the wrong divisor

**Primary source reopened:** vLLM #53142 remains open. The issue provides a concrete source-level mechanism and a verified patch on Qwen3.8-27B: hybrid Mamba state resume seeds the state column using `cache_config.block_size` even though the Mamba cache group has a different derived block size. A cached second request can compute a state index hundreds of columns beyond the block table and die in `precopy_mamba_align_fused_kernel`.

A related vLLM report, #54199, originally argued that block sizes were equal because the engine logged a 1600-token attention size. The reporter later **retracted that premise** after reading the source: the logged value was overwritten after that log line, while `mamba_block_size` retained the earlier value. The crash remained real but was #53142, not a separate bug.

**Two Minefield lessons:**

1. first request/cold path green does not validate cached-resume state indexing;
2. a startup log can truthfully print a value that is no longer the effective value by first forward.

Do not queue #54199 separately.

## R87-07 — “more precise” target numerics can make speculative decoding worse

**Primary source chain:** vLLM #49921 → merged PR #54048 (`b5707bf994cb968adfc7a29fbb80b0582f53f38d`).

The merged PR fixes family-120/GB10 being unnecessarily excluded from a cuBLAS BF16×BF16→FP32 router-GEMM path. The source-level bug is real and fixed upstream.

However, Reederey87's DSv4-Flash DSpark A/B in the issue thread is a deployment interaction worth preserving separately:

- new path engages and makes teacher-forced logits materially different;
- ordinary functional/long-context/composite gates stay green;
- speculative acceptance fell **0.638 → 0.574/0.574** (~10% relative), depressed at every draft slot;
- source conclusion: the old BF16-rounded target distribution was load-bearing for that drafter's agreement.

This is **not evidence that PR #54048 is wrong**. It is evidence that a target-side numerical fidelity improvement can invalidate a speculative drafter's acceptance assumptions. The current Reederey GLM-5.3 repo has just backported the merged router fix as W9; no GLM-5.3 MTP/DFlash acceptance verdict was found at the read head, so do not transfer the DSv4 number to GLM-5.3.

**Potential owner:** runtime upgrade changes target distribution while correctness stays green; re-qualify speculative acceptance after numerical kernel/path changes.

## R87-08 / R87-09 — dashboard cache metrics are not interchangeable with per-request cache truth

**Source:** commit `ddef9172a808def669c2b0626ec53ba13b7a91a3`, `docs/04-prefix-caching.md`.

Two separate metric-semantics claims:

1. Repo measurement says global `prefix_cache_queries/hits` deltas can over-count by **1.3–2× under queue pressure**, while per-request `usage.prompt_tokens_details.cached_tokens` is used as the primary ledger. The commit cites vLLM RFC #37003, but that RFC is about retention policy and does **not** by itself establish this exact counter-overcount mechanism. Keep this community-measured until a primary counter issue/code path is found.
2. `vllm:kv_cache_usage_perc` counts blocks held by **running** requests; a warm reusable cache can therefore report **0% at idle**. The source additionally reports page-granular accounting inflating occupancy relative to prompt tokens.

R87-09 is especially Minefield-shaped because a dashboard can simultaneously say “0% KV usage” and still have a highly effective warm cache.

## R87-10 — a memory-utilization knob can size nothing and still decide whether the server boots

**Source:** `docs/02-parameters.md`.

With explicit `--kv-cache-memory-bytes`, the repo says `gpu_memory_utilization` no longer sizes the pool; it only remains as the boot free-memory gate. On GB10 the gate follows CUDA device-free/`MemFree`, not `MemAvailable`, so host page cache can move the gate while the pinned KV bytes are unchanged. The repo reports 0.87 demanding ~105.87 GiB against boots varying ~104.1–106.98 GiB and causing crash loops.

**Portable lesson:** a flag can become inert for the function you think it controls while remaining active in a different decision path.

**Dedupe:** H30-01 already owns explicit KV pin bypassing automatic activation reserve. R87-10 is a different surface: `gpu_memory_utilization` becoming a *boot-only gate* after a pin.

## R87-11 — omission is not “off” when async is tri-state

**Source:** `docs/02-parameters.md`.

The kit requires `--no-async-scheduling`; simply omitting it resolves the tri-state default to ENABLED. Under this hybrid geometry the repo reports the async arm inflating the admission calculation to ~17.51 GiB and refusing to boot against the pin, while async-off passes and is throughput-neutral/slightly better in the cited benchmark.

The document cites vLLM #47728 “class,” but primary PR #47728 is specifically about settled-vs-scheduled token accounting/freeing under async and its consequential wider admission bound; it does not directly prove the exact 17.51 GiB calculation in this fork. Preserve this as community/fork measurement until the exact admission code path is pinned.

## R87-12 — the prebuilt image can hide a broken source-reproduction path

**Source:** commit `2c8233b781bc3c80100f8c60d6e473e24cca4423`.

An overlay file referenced by `Dockerfile COPY` had been removed from the repo. Existing runtime boots remained fine because the missing file was already baked into the pinned image. Only `BUILD=1` / clean image reproduction was broken. The repo later restored the file.

**Minefield lesson:** “the deployment still boots” does not prove “the published source can rebuild this deployment.”

**Dedupe:** strong concrete extension of H30-32 (binary/image identity does not establish source reproducibility).

## R87-13 — changing speculation can silently change cache geometry

**Source:** corrected/retracted vLLM #54199 observations.

The reporter preserved one valid observation after retracting the issue: on the tested Qwen hybrid path, MTP k=2 produced a derived Mamba/attention page around 1600 tokens while no speculation produced ~800. Therefore a test that toggles speculation is also changing cache/block geometry unless it explicitly controls/records it.

**Minefield value:** a nominal one-variable speculative A/B can move a second structural variable that changes prefix-cache behavior and state indexing.

## R87-14 — a Linux host reserve can masquerade as per-rank GPU-memory asymmetry on UMA

**Source:** `docs/01-architecture.md`, production parity checks.

On GB10 unified memory, the repo states `vm.min_free_kbytes` reserves memory from the GPU-visible pool (~1.25× the configured value on this deployment) and must match across nodes; asymmetry presents as phantom GPU-memory startup differences between otherwise matched ranks.

**Dedupe:** likely an extension of the GB10 UMA-accounting family (Traps 13/119/125), but the specific node-parity/sysctl mechanism is worth preserving.

## Existing-owner extensions / controls

- **R87-15:** vLLM `/health` may stay 200 through a stuck NCCL collective. Trap 112 readiness ladder owns the general lesson; add this as a distributed-forward-progress example if promoted.
- **R87-16:** failed systemd starts can leave wreckage and port ownership; Trap 53 restart/process-identity family.
- **R87-17:** `/health` can become green before a post-ready warmup is finished; benchmarking there pollutes throughput/spec counters. Trap 54/112 extension.
- **R87-18:** DFlash k=8: structured +2.5–3%, prose −9.1% because tail acceptance is low; direct Trap 111 workload-dependent speculative-value evidence.
- **R87-20:** first post-restart prose passes can read ~17% low during parked-swap fault-in; run-order/warm-state evidence, not a new model/runtime speed result.

## R87-19 — source evolution: #54199 must not be published as a separate crash mechanism

At read time, `docs/04-prefix-caching.md` still cites vLLM #54199 as a concurrent-hit crash caution. The issue itself is now titled **RETRACTED** and its sole closing comment says its core premise was wrong; the deterministic crash is explained by #53142's block-size divisor bug.

Minefield disposition: keep the useful test caution, but cite #53142 as the mechanism. Preserve #54199 only as another source-vetting example showing why linked issues must be re-opened at publication time.

## R87-21 — bearer auth is path-scoped, not server-global

**Source:** repo README's API-surface audit and local cache-reset patch behavior.

The kit notes that vLLM bearer middleware guards `/v1`, `/v2`, `/inference`, and `/cohere` prefixes. Root-mounted routes such as `/tokenize`/`/detokenize` and the locally exposed `/reset_prefix_cache` are outside those prefixes and answer without the key. The repo wisely binds loopback and disables the reset route for untrusted serving.

Minefield relevance: an operator can correctly configure an API key and still expose unauthenticated utility/state-changing endpoints if they assume auth wraps the entire HTTP server. Treat this as a security/serving-surface candidate; verify exact current upstream middleware before canonical promotion.

---

# Promotion / verification order

Best next work by value/cost:

1. **R87-01** stale shape-JIT A→B→A reproduction — high impact, likely distinct from U19.
2. **R87-05** primary vLLM #53142 adjudication for upstream tier; cheap source-level and deterministic two-request repro exists.
3. **R87-02** hybrid page-boundary veto — inspect #42317/#45238 and exact coordinator code, then decide upstream vs community.
4. **R87-03** dense-vs-sparse recurrent retention — source measured strongly; seek current vLLM #52216 semantics and cross-version reproduction.
5. **R87-09** confirm `kv_cache_usage_perc` exact semantics from current vLLM code; cheap and very reusable.
6. **R87-10** verify pin + `gpu_memory_utilization` effective behavior on a disposable GB10 boot.
7. **R87-13** record effective block/page geometry in any speculation A/B; likely easy to reproduce on Qwen hybrid lanes.
8. **R87-21** current auth middleware route-prefix audit; no GPU required.
9. **R87-07** run the newly merged router-GEMM path against GLM-5.3 DFlash/MTP acceptance before treating W9 as a free upgrade.
10. **R87-08/R87-11** locate the actual primary code/issue for the exact metric-overcount and admission-accounting claims before promotion.

# Attribution / claim boundary

All measurements above are from `Reederey87`'s public production-kit repository or the primary upstream threads it links; Blackwellboy has not reproduced them in this harvest. Credit stays with Reederey87 and the upstream reporters/maintainers. The source-vetting corrections are part of the finding: retracted #54199 is not a separate bug, and RFC #37003 does not independently prove the repo's exact global-counter inflation measurement.